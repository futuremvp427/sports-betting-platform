def success(data=None, message="ok"):
    return {
        "status": "success",
        "data": data,
        "message": message
    }


def error(message="error", data=None):
    return {
        "status": "error",
        "data": data,
        "message": message
    }
