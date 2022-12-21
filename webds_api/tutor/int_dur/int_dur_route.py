import numpy as np
from scipy.optimize import curve_fit

from .integration_duration import IntegrationDuration

def sigmoid(x, L ,x0, k, b):
    y = L / (1 + np.exp(-k*(x-x0))) + b
    return y

class IntDurRoute():
    def post(handle, input_data):
        request = input_data["request"]
        args = None
        if "arguments" in input_data:
            args = input_data["arguments"]

        idm = IntegrationDuration()

        if request == None:
            raise Exception("No request specified: ", input_data)

        if request == "sigmoid":
            xdata = input_data["sigmoid"]["xdata"]
            ydata = input_data["sigmoid"]["ydata"]
            sigma = np.ones(len(xdata))
            sigma[[0]] = 0.1
            p0 = [max(ydata), np.median(xdata), 1, min(ydata)]
            popt, pcov = curve_fit(sigmoid, xdata, ydata, p0, method='lm', maxfev=5000, sigma=sigma)
            return popt.tolist()

        try:
            retval = idm.function(request, args)
            return retval
        except Exception as e:
            raise Exception("Error executing {}: ".format(request), str(e))
