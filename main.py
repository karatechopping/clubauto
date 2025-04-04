import argparse
from datetime import datetime, timedelta
from src.data_fetcher import DataFetcher
from src.data_transformer import DataTransformer
from src.output_handlers.csv_handler import CSVHandler
from src.output_handlers.email_handler import EmailHandler
from src.output_handlers.ghl_handler import GHLHandler
from src.logger_config import setup_logging
import logging
import os
import glob
import pytz
from dotenv import load_dotenv
import sys

# Load environment variables from .env file if it exists
load_dotenv(override=True)

# Define the mappings (Daxko -> GHL)
field_mappings = {
    "FirstName": "firstName",
    "LastName": "lastName",
    "Email": "email",
    "PhoneCell": [
        "phone",
        {
            "ghl_field": "cellPhone",
            "ghl_id": "gSKZNaZWJDQgSIyQwDMr"
        },
    ],
    "StreetAddress": "address1",
    "City": "city",
    "State": "state",
    "Zip": [
        "postalCode",
        {
            "ghl_field": "zip",
            "ghl_id": "JRcvLEC9Z0d7rEFP6xDx"
        }
    ],
    "PhoneHome": {
        "ghl_field": "homePhone",
        "ghl_id": "NADASHNYlJVbnkKV6DmL"
    },
    "PhoneWork": {
        "ghl_field": "workPhone",
        "ghl_id": "lOA0OZrQQrcyyL6p6tWz"
    },
    "Gender": {
        "ghl_field": "what_is_your_gender",
        "ghl_id": "rTpK9ZnqlUoegSl27lRt"
    },
    "Status": {
        "ghl_field": "ca_status",
        "ghl_id": "PTRIDKO9282QhArQvQmx"
    },
    "SystemId": {
        "ghl_field": "ca_systemidnum",
        "ghl_id": "tFugHrHNDMSAICLG7zQA"
    },
    "OptOutStatus": {
        "ghl_field": "optoutstatus",
        "ghl_id": "es6cJSYAXZM8326B0Z9X"
    },
    "DeliveryMethod": {
        "ghl_field": "deliverymethod",
        "ghl_id": "lyckeY4wl04I9hVC3A9q"
    },
    "LastAPIUpdate": {
        "ghl_field": "last_api_update",
        "ghl_id": "DZXwU1OJbdBCzEXziB04"
    },
    "LiabilityWaiver": {
        "ghl_field": "ca_liabilitywaiver",
        "ghl_id": "6wwvA6psYtQ0srExNaqJ"
    },
    "UserGroupName": {
        "ghl_field": "ca_membership_type_1",
        "ghl_id": "DxXkT3nt0Za5eFMCj0v2"
    },
    "membership_type_2": {
        "ghl_field": "ca_membership_type_2",
        "ghl_id": "yGRuRsmOYH2AJFcjMkRR"
    },
    "membership_type_3": {
        "ghl_field": "ca_membership_type_3",
        "ghl_id": "lwrHOnrM56mKjXUbOGvF"
    },
    "membership_type_4": {
        "ghl_field": "ca_membership_type_4",
        "ghl_id": "vf5GH8ebre0UMYtBnzGA"
    },
    "membership_type_5": {
        "ghl_field": "ca_membership_type_5",
        "ghl_id": "0V5sPSxebwG0eQ5hbqYb"
    },
}

# Generate input_fields for fetcher
input_fields = list(field_mappings.keys())

# Create reverse mapping for CSV row 2
def create_reverse_mapping(field_mappings):
    reverse_map = {}
    for daxko_field, ghl_mapping in field_mappings.items():
        if isinstance(ghl_mapping, str):
            reverse_map[ghl_mapping] = daxko_field
        elif isinstance(ghl_mapping, list):
            for mapping in ghl_mapping:
                if isinstance(mapping, str):
                    reverse_map[mapping] = daxko_field
                elif isinstance(mapping, dict):
                    reverse_map[mapping["ghl_field"]] = daxko_field
        elif isinstance(ghl_mapping, dict):
            reverse_map[ghl_mapping["ghl_field"]] = daxko_field
    return reverse_map

def main():
    parser = argparse.ArgumentParser(description="Run data processing script.")
    parser.add_argument('--run_csv', type=lambda x: (str(x).lower() == 'true'), default=False, help='Whether to run CSV processing.')
    parser.add_argument('--run_ghl', type=lambda x: (str(x).lower() == 'true'), default=False, help='Whether to run GHL processing.')
    parser.add_argument('--run_email', type=lambda x: (str(x).lower() == 'true'), default=False, help='Whether to run email processing.')
    parser.add_argument('--attach_csv', type=lambda x: (str(x).lower() == 'true'), default=False, help='Whether to attach CSV to email.')
    parser.add_argument('--sample_size', type=int, default=-1, help='Sample size for processing.')
    parser.add_argument('--days_back', type=int, default=None, help='Number of days to go back.')
    parser.add_argument('--run_log', type=lambda x: (str(x).lower() == 'true'), default=True, help='Whether to run logging.')

    args = parser.parse_args()

    # Setup logging first
    run_log = args.run_log
    log_file = setup_logging(filename="dummy.log") if not run_log else setup_logging()
    logger = logging.getLogger(__name__)

    # Determine criteria_fields based on days_back
    days_back = args.days_back
    if days_back is not None:
        try:
            days_back = int(days_back)
            if days_back > 0:
                central_tz = pytz.timezone('America/Chicago')
                today = datetime.now(central_tz)
                from_date = today - timedelta(days=days_back - 1)
                to_date_str = today.strftime("%m/%d/%Y")
                from_date_str = from_date.strftime("%m/%d/%Y")
                criteria_fields = {
                    "user": {
                        "profileCreation": {
                            "from": from_date_str,
                            "to": to_date_str
                        }
                    }
                }
                logger.info(f"Using date range criteria: from {from_date_str} to {to_date_str}")
                print(f"Using date range criteria: from {from_date_str} to {to_date_str}")
            else:
                criteria_fields = {"user": {"gender": "0"}}
                logger.info("Using default gender criteria")
                print("Using default gender criteria")
        except ValueError:
            criteria_fields = {"user": {"gender": "0"}}
            logger.info("Invalid days_back value. Using default gender criteria")
            print("Invalid days_back value. Using default gender criteria")
    else:
        criteria_fields = {"user": {"gender": "0"}}
        logger.info("No days_back provided. Using default gender criteria")
        print("No days_back provided. Using default gender criteria")

    logger.info("Starting processing run")
    logger.info(f"GHL_LOCATION: {os.environ.get('GHL_LOCATION', 'Not Set')}")

    central_tz = pytz.timezone('America/Chicago')
    timestamp = datetime.now(central_tz).strftime("%Y-%m-%d_%H%M%S")
    logger.info(f"Timestamp created: {timestamp}")

    logger.info(f"Current ENV: SMTP_PASSWORD exists? {'SMTP_PASSWORD' in os.environ}")
    logger.info(f"PYTHONPATH: {os.environ.get('PYTHONPATH')}")
    logger.info(f"Current working directory: {os.getcwd()}")

    # Initialize components
    logger.info("Initializing components...")
    fetcher = DataFetcher(criteria_fields)
    transformer = DataTransformer(field_mappings)

    # Results tracking
    results = {
        'csv_files': None,
        'csv_stats': {'valid': 0, 'invalid': 0},
        'ghl_stats': {
            'success': 0,
            'failed': 0,
            'added': 0,
            'updated': 0
        },
        'status': {
            'csv': 'Not Started',
            'ghl': 'Not Started'
        }
    }

    try:
        # Step 1: Fetch raw data from Daxko
        logger.info("Fetching data from Daxko API...")
        raw_data = fetcher.get_data(input_fields)

        if raw_data.get("data"):
            logger.info(f"Successfully fetched {len(raw_data['data'])} records")

            # Step 2: Transform the data
            logger.info("Transforming data...")
            transformed_data = transformer.transform_data(raw_data["data"])

            # Apply sample size if specified
            sample_size = args.sample_size
            if sample_size > 0:
                transformed_data['valid'] = transformed_data['valid'][:sample_size]
                logger.info(f"Applied sample size: {sample_size}")

            logger.info(f"Transformed {len(transformed_data['valid'])} valid contacts")
            logger.info(f"Found {len(transformed_data['invalid'])} invalid contacts")

            # Step 3: Write to CSV (if enabled)
            run_csv = args.run_csv
            if run_csv:
                logger.info("Writing data to CSV...")
                csv_handler = CSVHandler(create_reverse_mapping(field_mappings))
                results['csv_files'] = csv_handler.write_csv(transformed_data, timestamp)
                results['csv_stats'] = {
                    'valid': len(transformed_data['valid']),
                    'invalid': len(transformed_data['invalid'])
                }
                results['status']['csv'] = 'Completed'
                logger.info(f"CSV files created: {results['csv_files']}")
            else:
                results['status']['csv'] = 'Skipped'
                logger.info("CSV generation skipped")

            # Step 4: Update GHL via API (if enabled)
            run_ghl = args.run_ghl
            if run_ghl:
                logger.info("Processing contacts in GHL...")
                ghl_handler = GHLHandler()
                ghl_results = ghl_handler.process_contacts(transformed_data['valid'])
                results['ghl_stats'] = ghl_results['ghl_stats']
                results['status']['ghl'] = 'Completed'
                logger.info("GHL processing complete")
            else:
                results['status']['ghl'] = 'Skipped'
                logger.info("GHL processing skipped")

            # Step 5: Send email (if enabled)
            run_email = args.run_email
            attach_csv = args.attach_csv
            if run_email:
                logger.info("Sending email report...")
                email_handler = EmailHandler()
                email_handler.send_report(results, timestamp, run_csv, attach_csv)
                logger.info("Email sent successfully")
            else:
                logger.info("Email sending skipped")

        else:
            logger.warning("No data fetched from the API.")

    except Exception as e:
        logger.error(f"Error during process: {e}")
        raise

    finally:
        if not run_log:
            if os.path.exists("dummy.log"):
                os.remove("dummy.log")
                logger.info("Deleted dummy.log")

    return results

def tidy_up_files(directory, pattern, max_files):
    """Keep only the latest `max_files` in `directory` matching `pattern`."""
    files = sorted(glob.glob(os.path.join(directory, pattern)), key=os.path.getmtime, reverse=True)
    for old_file in files[max_files:]:
        os.remove(old_file)
        logger.info(f"Deleted old file: {old_file}")

if __name__ == "__main__":
    logger = logging.getLogger(__name__)
    logger.info("Script starting...")

    main()

    # Tidy up old CSV and log files
    logger.info("Tidying up old files...")
    tidy_up_files("csv", "*.csv", 20)
    tidy_up_files("logs", "*.log", 10)

    logger.info("Script completed")
