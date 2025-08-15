


STRING_NULL_VALUES = {
    "",
    "N/A",
    "null",
    "string"
}


def replace_null_values(data: any) -> any:
    if isinstance(data, list):
        return [replace_null_values(item) for item in data]
    elif isinstance(data, dict):
        for key, value in data.items():
            data[key] = replace_null_values(value)
        return data
    elif isinstance(data, str):
        if data in STRING_NULL_VALUES:
            return None
    return data

