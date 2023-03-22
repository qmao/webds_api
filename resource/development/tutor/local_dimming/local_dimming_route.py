from ...touchcomm.touchcomm_manager import TouchcommManager
from .local_dimming import LocalDimming


class LocalDimmingRoute():
    _tutor = None

    def post(handle, input_data):
        request = input_data["request"]
        args = None
        if "arguments" in input_data:
            args = input_data["arguments"]

        if LocalDimmingRoute._tutor is None:
            tc = TouchcommManager().getInstance()
            LocalDimmingRoute._tutor = LocalDimming(tc)

        if request == None:
            raise Exception("No request specified: ", input_data)

        retval = None
        try:
            tutor_function = getattr(LocalDimmingRoute._tutor, request)
            if args is None:
                retval = tutor_function()
            else:
                retval = tutor_function(*args)
        except Exception as e:
            raise Exception("Error executing {}: ".format(request), str(e))

        return retval
