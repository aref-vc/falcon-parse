import os
import json
import pandas as pd
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime
import tempfile
import re

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class DataProcessor:
    def __init__(self):
        self.temp_dir = "/tmp"
        os.makedirs(self.temp_dir, exist_ok=True)
    
    def process_data(self, raw_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Process and clean the raw extracted data
        """
        if not raw_data:
            return {"data": [], "columns": [], "summary": "No data found"}
        
        logger.info(f"Processing {len(raw_data)} raw data items")
        
        try:
            # Clean and normalize the data
            cleaned_data = self._clean_data(raw_data)
            
            # Extract column names
            columns = self._extract_columns(cleaned_data)
            
            # Generate summary statistics
            summary = self._generate_summary(cleaned_data, columns)
            
            return {
                "data": cleaned_data,
                "columns": columns,
                "summary": summary,
                "processed_at": datetime.now().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Data processing failed: {e}")
            return {
                "data": raw_data,  # Return raw data as fallback
                "columns": list(raw_data[0].keys()) if raw_data else [],
                "summary": f"Processing failed: {str(e)}",
                "processed_at": datetime.now().isoformat()
            }
    
    def _clean_data(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Clean and normalize data items with consistent field ordering"""
        cleaned_data = []
        
        for item in data:
            if not isinstance(item, dict):
                continue
                
            cleaned_item = {}
            
            for key, value in item.items():
                # Clean the key
                clean_key = self._clean_field_name(key)
                
                # Clean the value
                clean_value = self._clean_field_value(value)
                
                cleaned_item[clean_key] = clean_value
            
            if cleaned_item:  # Only add non-empty items
                cleaned_data.append(cleaned_item)
        
        # Remove duplicates
        cleaned_data = self._remove_duplicates(cleaned_data)
        
        # Reorder fields consistently in each item
        cleaned_data = self._reorder_data_fields(cleaned_data)
        
        logger.info(f"Cleaned data: {len(cleaned_data)} items")
        return cleaned_data
    
    def _reorder_data_fields(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Reorder fields in each data item according to logical priority"""
        if not data:
            return data
        
        # Get the consistent column order
        columns = self._extract_columns(data)
        
        # Reorder each item according to the column priority
        reordered_data = []
        for item in data:
            reordered_item = {}
            
            # Add fields in the proper order - include ALL columns even if null
            for column in columns:
                reordered_item[column] = item.get(column, None)
            
            reordered_data.append(reordered_item)
        
        return reordered_data
    
    def _clean_field_name(self, field_name: str) -> str:
        """Clean and normalize field names"""
        if not isinstance(field_name, str):
            field_name = str(field_name)
        
        # Convert to lowercase and replace spaces/special chars with underscores
        clean_name = re.sub(r'[^a-zA-Z0-9]+', '_', field_name.lower())
        
        # Remove leading/trailing underscores
        clean_name = clean_name.strip('_')
        
        # Ensure it starts with a letter
        if clean_name and clean_name[0].isdigit():
            clean_name = 'field_' + clean_name
        
        return clean_name or 'unknown_field'
    
    def _clean_field_value(self, value: Any) -> Any:
        """Clean and normalize field values"""
        if value is None:
            return None
        
        if isinstance(value, str):
            # Strip whitespace
            value = value.strip()
            
            # Remove excessive whitespace
            value = re.sub(r'\s+', ' ', value)
            
            # Return None for empty strings
            if not value:
                return None
            
            # Try to detect and convert common data types
            return self._auto_convert_type(value)
        
        elif isinstance(value, (int, float, bool)):
            return value
        
        elif isinstance(value, (list, dict)):
            # Convert complex types to strings
            return str(value)
        
        else:
            return str(value)
    
    def _auto_convert_type(self, value: str) -> Any:
        """Automatically convert string values to appropriate types"""
        # Try to convert to number
        try:
            # Check if it's an integer
            if value.isdigit() or (value.startswith('-') and value[1:].isdigit()):
                return int(value)
            
            # Check if it's a float
            float_val = float(value)
            return float_val
        except ValueError:
            pass
        
        # Check for boolean values
        lower_val = value.lower()
        if lower_val in ['true', 'yes', 'on', '1']:
            return True
        elif lower_val in ['false', 'no', 'off', '0']:
            return False
        
        # Check for null/empty values
        if lower_val in ['null', 'none', 'n/a', 'na', '']:
            return None
        
        # Return as string
        return value
    
    def _remove_duplicates(self, data: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Remove duplicate items from the data"""
        seen = set()
        unique_data = []
        
        for item in data:
            # Create a hashable representation of the item
            item_signature = tuple(sorted(item.items()))
            
            if item_signature not in seen:
                seen.add(item_signature)
                unique_data.append(item)
        
        if len(unique_data) < len(data):
            logger.info(f"Removed {len(data) - len(unique_data)} duplicate items")
        
        return unique_data
    
    def _extract_columns(self, data: List[Dict[str, Any]]) -> List[str]:
        """Extract all unique column names from the data with logical ordering"""
        if not data:
            return []
        
        all_columns = set()
        for item in data:
            all_columns.update(item.keys())
        
        # Define logical column ordering priorities
        column_priorities = {
            # Identity fields (highest priority)
            'name': 0,
            'first_name': 1,
            'last_name': 2,
            'full_name': 3,
            'family_name': 4,
            
            # Title and role
            'title': 10,
            'role': 11,
            'position': 12,
            'job_title': 13,
            
            # Organization
            'company': 20,
            'organization': 21,
            'affiliation': 22,
            'employer': 23,
            'department': 24,
            
            # Contact information
            'email': 30,
            'phone': 31,
            'mobile': 32,
            'telephone': 33,
            
            # Social media (in logical order)
            'linkedin': 40,
            'twitter': 41,
            'x_twitter': 42,
            'github': 43,
            'website': 44,
            'personal_website': 45,
            'instagram': 46,
            'facebook': 47,
            'youtube': 48,
            'tiktok': 49,
            
            # Location
            'location': 60,
            'address': 61,
            'city': 62,
            'state': 63,
            'country': 64,
            
            # Additional details
            'description': 70,
            'bio': 71,
            'summary': 72,
            'about': 73,
            
            # Product/Business specific
            'price': 80,
            'cost': 81,
            'value': 82,
            'availability': 83,
            'status': 84,
            'category': 85,
            'brand': 86,
            
            # Dates and times
            'date': 90,
            'created_at': 91,
            'updated_at': 92,
            'published': 93,
            
            # URLs and links
            'url': 100,
            'link': 101,
            'source': 102,
            
            # Generic fields (lowest priority)
            'id': 110,
            'uuid': 111,
            'index': 112
        }
        
        def get_priority(column_name: str) -> int:
            """Get priority for column ordering"""
            # Check exact match first
            if column_name in column_priorities:
                return column_priorities[column_name]
            
            # Check for partial matches (contains key words)
            for key_word, priority in column_priorities.items():
                if key_word in column_name.lower():
                    return priority + 0.5  # Slightly lower priority for partial matches
            
            # Default priority for unknown fields
            return 1000
        
        # Sort columns by priority, then alphabetically
        sorted_columns = sorted(
            all_columns, 
            key=lambda col: (get_priority(col), col.lower())
        )
        
        return sorted_columns
    
    def _generate_summary(self, data: List[Dict[str, Any]], columns: List[str]) -> Dict[str, Any]:
        """Generate summary statistics about the data"""
        if not data:
            return {"total_rows": 0, "total_columns": 0}
        
        summary = {
            "total_rows": len(data),
            "total_columns": len(columns),
            "columns": columns
        }
        
        # Add column-specific statistics
        column_stats = {}
        for col in columns:
            col_values = [item.get(col) for item in data]
            non_null_values = [v for v in col_values if v is not None]
            
            col_stat = {
                "non_null_count": len(non_null_values),
                "null_count": len(col_values) - len(non_null_values),
                "data_types": list(set(type(v).__name__ for v in non_null_values))
            }
            
            # Add unique count for categorical data
            if non_null_values:
                unique_values = set(str(v) for v in non_null_values)
                col_stat["unique_count"] = len(unique_values)
                
                # If small number of unique values, include them
                if len(unique_values) <= 10:
                    col_stat["unique_values"] = sorted(list(unique_values))
            
            column_stats[col] = col_stat
        
        summary["column_statistics"] = column_stats
        return summary
    
    def generate_exports(self, job_id: str, processed_data: Dict[str, Any]) -> Dict[str, str]:
        """Generate JSON and CSV export files"""
        data = processed_data.get("data", [])
        
        if not data:
            logger.warning("No data to export")
            return {}
        
        try:
            # Generate JSON export
            json_path = self._generate_json_export(job_id, processed_data)
            
            # Generate CSV export
            csv_path = self._generate_csv_export(job_id, data)
            
            logger.info(f"Generated exports for job {job_id}")
            return {
                "json": json_path,
                "csv": csv_path
            }
            
        except Exception as e:
            logger.error(f"Export generation failed: {e}")
            raise Exception(f"Failed to generate exports: {str(e)}")
    
    def _generate_json_export(self, job_id: str, processed_data: Dict[str, Any]) -> str:
        """Generate JSON export file"""
        file_path = os.path.join(self.temp_dir, f"falcon_parse_{job_id}.json")
        
        export_data = {
            "metadata": {
                "job_id": job_id,
                "exported_at": datetime.now().isoformat(),
                "tool": "Falcon Parse",
                "summary": processed_data.get("summary", {})
            },
            "data": processed_data.get("data", []),
            "columns": processed_data.get("columns", [])
        }
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(export_data, f, indent=2, ensure_ascii=False)
        
        logger.info(f"JSON export created: {file_path}")
        return file_path
    
    def _generate_csv_export(self, job_id: str, data: List[Dict[str, Any]]) -> str:
        """Generate CSV export file with consistent column ordering"""
        file_path = os.path.join(self.temp_dir, f"falcon_parse_{job_id}.csv")
        
        if not data:
            # Create empty CSV with headers
            pd.DataFrame().to_csv(file_path, index=False)
            return file_path
        
        # Get consistent column order
        columns = self._extract_columns(data)
        
        # Convert to DataFrame with consistent column order
        df = pd.DataFrame(data, columns=columns)
        
        # Handle mixed data types
        for col in df.columns:
            # Convert any remaining complex objects to strings
            df[col] = df[col].apply(lambda x: str(x) if isinstance(x, (dict, list)) else x)
        
        # Export to CSV with consistent column order
        df.to_csv(file_path, index=False, encoding='utf-8')
        
        logger.info(f"CSV export created: {file_path} with {len(columns)} columns in logical order")
        return file_path
    
    def cleanup_old_files(self, hours_old: int = 24):
        """Clean up old export files"""
        try:
            current_time = datetime.now().timestamp()
            cutoff_time = current_time - (hours_old * 3600)
            
            removed_count = 0
            for filename in os.listdir(self.temp_dir):
                if filename.startswith("falcon_parse_"):
                    file_path = os.path.join(self.temp_dir, filename)
                    if os.path.getmtime(file_path) < cutoff_time:
                        os.remove(file_path)
                        removed_count += 1
            
            if removed_count > 0:
                logger.info(f"Cleaned up {removed_count} old export files")
                
        except Exception as e:
            logger.error(f"File cleanup failed: {e}")