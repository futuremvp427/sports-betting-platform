def basic_security_checks(request_data):
    if not request_data:
        return False
    if "<script>" in str(request_data):
        return False
    return True
