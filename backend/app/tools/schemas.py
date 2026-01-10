from typing import Any, Dict, List, Optional, Type
from pydantic import BaseModel, Field, create_model

def create_tool_validator(tool_name: str, parameters_schema: Dict[str, Any]) -> Type[BaseModel]:
    """
    Creates a Pydantic model class dynamically from a JSON Schema-like parameters definition.
    This allows validation to be config-driven based on chat_config.json.
    """
    fields: Dict[str, Any] = {}
    props = parameters_schema.get("properties", {})
    required = set(parameters_schema.get("required", []))
    
    for field_name, field_def in props.items():
        # Map JSON schema types to Python types
        json_type = field_def.get("type", "string")
        python_type = str
        
        if json_type == "integer":
            python_type = int
        elif json_type == "number":
            python_type = float
        elif json_type == "boolean":
            python_type = bool
        elif json_type == "array":
            python_type = list
        elif json_type == "object":
            python_type = dict
            
        # Determine if required
        is_req = field_name in required
        
        # Determine default value
        default_val = field_def.get("default")
        
        if is_req and default_val is None:
            # Required field, no default
            field_info = Field(...)
            annotation = python_type
        else:
            # Optional or has default
            field_info = Field(default=default_val)
            annotation = Optional[python_type]
            
        fields[field_name] = (annotation, field_info)
        
    # Configure model to forbid extra fields if specified in schema or strictly by default
    # The config says "additionalProperties": false usually
    extra_behavior = "forbid" if parameters_schema.get("additionalProperties") is False else "ignore"
    
    model_config = {
        "extra": extra_behavior
    }
    
    # Create the dynamic model
    return create_model(
        f"{tool_name}_Validator",
        __config__=model_config,
        **fields
    )
