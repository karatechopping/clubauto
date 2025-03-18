import re

class DataTransformer:
    def __init__(self, field_mappings):
        """
        Initialize the DataTransformer with field mappings.
        :param field_mappings: Combined mappings for standard and custom GHL fields.
        """
        self.field_mappings = field_mappings
        self.email_pattern = re.compile(r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$')

    def is_valid_email(self, email):
        """Check if email is valid."""
        if not email:
            return False
        return bool(self.email_pattern.match(email))

    def is_valid_phone(self, phone):
        """Check if phone is valid."""
        if not phone:
            return False
        # Strip any non-numeric characters
        phone = ''.join(filter(str.isdigit, str(phone)))
        # Basic check for length - adjust as needed
        return len(phone) >= 10

    def is_valid_record(self, record):
        """
        Check if record has either valid email or valid phone.
        """
        email = record.get('email', '')
        phone = record.get('phone', '')

        has_valid_email = self.is_valid_email(email)
        has_valid_phone = self.is_valid_phone(phone)

        return has_valid_email or has_valid_phone

    def transform_data(self, raw_data):
        """Transform raw Daxko data into a standardized format."""
        grouped_data = {}
        valid_records = []
        invalid_records = []

        # First pass: Group by SystemId and collect membership types
        for record in raw_data:
            member_id = record.get("SystemId")
            if not member_id:
                continue

            if member_id not in grouped_data:
                grouped_data[member_id] = {
                    "record": record,
                    "membership_types": [""] * 5,
                }

            membership_type = record.get("UserGroupName")
            if membership_type:
                for i in range(5):
                    if grouped_data[member_id]["membership_types"][i] == "":
                        grouped_data[member_id]["membership_types"][i] = membership_type
                        break

        # Second pass: Transform and validate
        for member_data in grouped_data.values():
            record = member_data["record"]
            transformed_record = {}

            # Apply field mappings
            for daxko_field, mapping in self.field_mappings.items():
                value = record.get(daxko_field, "")

                if isinstance(mapping, str):
                    transformed_record[mapping] = value
                elif isinstance(mapping, list):
                    for map_item in mapping:
                        if isinstance(map_item, str):
                            transformed_record[map_item] = value
                        elif isinstance(map_item, dict):
                            transformed_record[map_item["ghl_field"]] = value
                            transformed_record[f"{map_item['ghl_field']}_id"] = map_item["ghl_id"]
                elif isinstance(mapping, dict):
                    transformed_record[mapping["ghl_field"]] = value
                    transformed_record[f"{mapping['ghl_field']}_id"] = mapping["ghl_id"]

            # Add membership types
            for i in range(5):
                transformed_record[f"membership_type_{i + 1}"] = member_data["membership_types"][i]

            # Clean up email and phone if present
            if 'email' in transformed_record:
                email = transformed_record['email']
                transformed_record['email'] = email.strip().lower() if email else None

            if 'phone' in transformed_record:
                phone = transformed_record['phone']
                transformed_record['phone'] = ''.join(filter(str.isdigit, str(phone))) if phone else None


            # Validate and sort
            if self.is_valid_record(transformed_record):
                valid_records.append(transformed_record)
            else:
                invalid_records.append(transformed_record)

        return {
            'valid': valid_records,
            'invalid': invalid_records
        }
