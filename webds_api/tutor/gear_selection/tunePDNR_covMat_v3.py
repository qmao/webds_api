#!/usr/bin/env python

#version information
# DS6Result:scriptVersion=3

from __future__ import print_function

#from ds6_xml import parse_xml_log

from argparse import ArgumentParser
from sys import exit

from numpy import dot, int16, float64, set_printoptions, sqrt, zeros, zeros_like
from numpy import copy, transpose, ones_like, tile, divide
from numpy import reshape, pad, diag
from numpy.linalg import lstsq, svd
from numpy.random import randn, seed


BASELINE_WINDOW_LEN = 101
ADNS_MOD_STDEV_FACTOR = 0.25
RNG_SEED = 103750987
TRAINING_FRACTION = 0.9  # split into training and evaluation

def parse_args():
    parser = ArgumentParser()
    parser.add_argument("noise_logfile", help="log file containing noise frames for PDNR training")
    return parser.parse_args()

def compensate_adns(finger_scale, x):
    """
    Compensate ADNS in the training data by adding random common-mode offsets.
    """
    x += ADNS_MOD_STDEV_FACTOR * finger_scale * randn(*x.shape[:-1])[..., None]  # add a random offset that is common per last-axis

def compute_moving_baseline(noise_raw):
    """
    Compute a moving average baseline. Only ever average windows of the full
    window length. The boundaries will repeat the first/last full average.
    We use a local baseline average to mitigate thermal drift.
    """
    if len(noise_raw) < BASELINE_WINDOW_LEN:
        raise ValueError("need at least {} frames of data".format(BASELINE_WINDOW_LEN))
    half_len = BASELINE_WINDOW_LEN // 2
    temp = noise_raw.cumsum(axis=0)
    out = zeros_like(noise_raw)
    out[half_len+1:-half_len] = (temp[BASELINE_WINDOW_LEN:] - temp[:-BASELINE_WINDOW_LEN]) / BASELINE_WINDOW_LEN
    out[:half_len+1] = out[half_len+1]
    out[-half_len:] = out[-half_len-1]
    return out

def do_gain_compensation(trans_delta, config):
    """
    Apply gain compensation to trans delta data
    NOTE: Based on empirical results, we only apply
    gain compensation for fully cut out pixels
    """
    if config.get("applyCutOutGain", False):

        cutOutLength = config["cutOutLength"]
        cutOutRows = config["cutOutRows"]
        cutOutCols = config["cutOutCols"]
        cutOutFraction = config["cutOutFraction"]

        for row, col, frac in zip(cutOutRows[:cutOutLength], cutOutCols, cutOutFraction):
            if frac < 0.001:
                trans_delta[:, row, col] = 0

    return trans_delta

def append_notch_mask(mask, config):
    """
    The mask is updated to 0 at fully cut out pixel locations.
    """
    cutOutLength = config["cutOutLength"]
    cutOutRows = config["cutOutRows"]
    cutOutCols = config["cutOutCols"]
    cutOutFraction = config["cutOutFraction"]

    for row, col, frac in zip(cutOutRows[:cutOutLength], cutOutCols, cutOutFraction):
        if frac < 0.001:
            mask[row, col] = False

    return mask

def append_corner_mask(mask):
    """
    The mask is updated to 0 at corner pixels.
    """
    mask[0, 0] = False
    mask[0, -1] = False
    mask[-1, 0] = False
    mask[-1, -1] = False

    return mask


def images_to_rows(images):
    rx_count = images.shape[2]
    return images.reshape((-1, rx_count))

def rows_to_images(rows, tx_count, rx_count):
    return rows.reshape((-1, tx_count, rx_count))

def choose_principal_components(x, order=4, mask_rows=None):
    """
    The input x is assumed to be arranged with each observation as a row.
    The input notch_mask_rows contains the corresponding notch mask for each row of x.
    The output has basis vectors in rows.
    """

    if mask_rows is not None:
        x[mask_rows == False] = 0
        scale_matrix = dot(mask_rows.T, mask_rows) / mask_rows.shape[0]
        xTx = divide(dot(x.T, x), scale_matrix)
    else:
        xTx = dot(x.T, x)

    u, s, v = svd(xTx)
    return s[:order], v[:order, :]

def apply_pdnr(basis, x, mask=None):
    """
    basis is `order` column vectors.
    x is a matrix of row vectors.
    """
    if mask is None:  # assumes orthonormality
        amplitudes = dot(basis, x.T)
    else:
        B = basis[:, mask]
        amplitudes = lstsq(B.T, x[:, mask].T)[0]
    fit = dot(amplitudes.T, basis)
    clean = x - fit
    return clean

def constructTuning(config, trans_basis, trans_stdevs, profx_basis=None, profx_stdevs=None, profy_basis=None, profy_stdevs=None, noise_trans=None):
    """
    Creating the tuning dictionary.
    """
    tuning = {}

    tuning["basisAmpStdevTransRx"] = ", ".join("{:.5f}".format(s) for s in trans_stdevs)
    tuning["basisVectorsTransRx"] = ", ".join("{:d}".format(b) for b in (32768 * trans_basis.T).round().astype(int16).ravel())

    if profx_basis is not None:
        tuning["basisAmpStdevAbsRx"] = ", ".join("{:.5f}".format(s) for s in profx_stdevs)
        tuning["basisVectorsAbsRx"] = ", ".join("{:d}".format(b) for b in (32768 * profx_basis.T).round().astype(int16).ravel())
        tuning["basisAmpStdevAbsTx"] = ", ".join("{:.5f}".format(s) for s in profy_stdevs)
        tuning["basisVectorsAbsTx"] = ", ".join("{:d}".format(b) for b in (32768 * profy_basis.T).round().astype(int16).ravel())

    # NSM needs its own basis vectors, for now.
    # While PDNR wants column vectors of signed 1p15, NSM wants row vectors of int8p8.
    if config.get("updatePdnrConfigData", False) and noise_trans is not None:
        # Each vector must be of length MAX_RX to match data in static config
        pad_width = len(config["imageRxes"]) - noise_trans.shape[2]
        trans_basis_padded = pad(trans_basis,pad_width=((0,0),(0,pad_width)),mode='constant')
        tuning["pdnrConfigData"] = ", ".join("{:d}".format(b) for b in (256 * trans_basis_padded).round().astype(int16).ravel())

    return tuning

def tunePDNR(config, noise_trans, noise_profx, noise_profy):
    """
    Tune PDNR. Return a dictionary of config and their values. The values are output as strings that
    can literally be copy-pasted into a DS6 advanced view text box.
    """
    pdnrOrder = len(config["ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx"]) - 1  # have one stdev per order plus residual

    noise_trans = noise_trans.astype(float64)
    noise_profx = noise_profx.astype(float64)
    noise_profy = noise_profy.astype(float64)

    if config["adnsEnabled"]:
        seed_value = config.get("FirmwareBuildId", RNG_SEED)
        seed(seed_value)  # we don't care what the seed is, but we want reproducible results
        compensate_adns(config["saturationLevel"], noise_trans)

    trans_bl = compute_moving_baseline(noise_trans)
    noise_trans_delta = trans_bl - noise_trans
    noise_trans_delta = do_gain_compensation(noise_trans_delta, config)
    NT = int(TRAINING_FRACTION * len(noise_trans_delta))
    noise_trans_rows = images_to_rows(noise_trans_delta[:NT])

    trans_mask = ones_like(noise_trans[0], dtype=bool)

    if config.get("applyCutOutGain", False):
        trans_mask = append_notch_mask(trans_mask, config)

    if config.get("pdnrCornerExclusion", False):
        trans_mask = append_corner_mask(trans_mask)

    if not (trans_mask == False).any():
        trans_sv, trans_basis = choose_principal_components(noise_trans_rows, pdnrOrder)
    else:
        trans_mask_rows = images_to_rows(tile(trans_mask.astype(float64),[noise_trans.shape[0],1,1]))
        trans_sv, trans_basis = choose_principal_components(noise_trans_rows, pdnrOrder, trans_mask_rows[:NT])

    noise_trans_eval = images_to_rows(noise_trans_delta[NT:])
    noise_trans_resid = apply_pdnr(trans_basis, noise_trans_eval)
    trans_stdevs = zeros((pdnrOrder + 1,), dtype=float)
    trans_stdevs[:-1] = sqrt(trans_sv / len(noise_trans_rows))
    trans_stdevs[-1] = noise_trans_resid.std(axis=0).max()

    if config["hasProfiles"]:
        NT = int(TRAINING_FRACTION * len(noise_profx))
        if config["adnsEnabled"]:
            compensate_adns(config["profileAmplitudeX"], noise_profx)
        profx_bl = compute_moving_baseline(noise_profx)
        noise_profx_delta = noise_profx - profx_bl
        profx_sv, profx_basis = choose_principal_components(noise_profx_delta[:NT], pdnrOrder)
        noise_profx_resid = apply_pdnr(profx_basis, noise_profx_delta[NT:])
        profx_stdevs = zeros((pdnrOrder + 1,), dtype=float)
        profx_stdevs[:-1] = sqrt(profx_sv / NT)
        profx_stdevs[-1] = noise_profx_resid.std(axis=0).max()

        if config["adnsEnabled"]:
            compensate_adns(config["profileAmplitudeY"], noise_profy)
        profy_bl = compute_moving_baseline(noise_profy)
        noise_profy_delta = noise_profy - profy_bl
        profy_sv, profy_basis = choose_principal_components(noise_profy_delta[:NT], pdnrOrder)
        noise_profy_resid = apply_pdnr(profy_basis, noise_profy_delta[NT:])
        profy_stdevs = zeros((pdnrOrder + 1,), dtype=float)
        profy_stdevs[:-1] = sqrt(profy_sv / NT)
        profy_stdevs[-1] = noise_profy_resid.std(axis=0).max()
    else:
        profx_basis = None
        profx_stdevs = None
        profy_basis = None
        profy_stdevs = None

    tuning = constructTuning(config, trans_basis, trans_stdevs, profx_basis, profx_stdevs, profy_basis, profy_stdevs, noise_trans)

    return tuning

def pdnrTuningFromCovMats(config, nNoiseConditions=1, nFrames=400, ntx=20, xTx_trans=None, xTx_profx=None, xTx_profy=None):

    if nNoiseConditions > 1:
        if len(xTx_trans.shape) != 3:
            raise ValueError("need an array of covariance matrices for xTx_trans when nNoiseConditions is greater than 1")
        xTx_trans = sum(xTx_trans, 0)

        if xTx_profx is not None:
            if len(xTx_profx.shape) != 3:
                raise ValueError("need an array of covariance matrices for xTx_profx when nNoiseConditions is greater than 1")
            xTx_profx = sum(xTx_profx, 0)

        if xTx_profy is not None:
            if len(xTx_profy.shape) != 3:
                raise ValueError("need an array of covariance matrices for xTx_profy when nNoiseConditions is greater than 1")
            xTx_profy = sum(xTx_profy, 0)

    elif nNoiseConditions == 1:
        if len(xTx_trans.shape) == 3:
            xTx_trans = sum(xTx_trans, 0)

        if len(xTx_trans.shape) != 2:
            raise ValueError("array of covariance matrices for xTx_trans of incorrect size")

        if xTx_profx is not None:
            if len(xTx_profx.shape) == 3:
                xTx_profx = sum(xTx_profx, 0)

            if len(xTx_profx.shape) != 2:
                raise ValueError("array of covariance matrices for xTx_profx of incorrect size")

        if xTx_profy is not None:
            if len(xTx_profy.shape) == 3:
                xTx_profy = sum(xTx_profy, 0)

            if len(xTx_profy.shape) != 2:
                raise ValueError("array of covariance matrices for xTx_profy of incorrect size")

    pdnrOrder = len(config["ifpConfig.pdnrConfigs[0].basisAmpStdevAbsRx"]) - 1  # have one stdev per order plus residual
    reduceOrderForADNS = 0
    if config["adnsEnabled"]:
        reduceOrderForADNS = 1

    u, s, v = svd(xTx_trans)
    trans_noise_resid = dot(v[pdnrOrder:,:].T, dot(diag(s[pdnrOrder:]), v[pdnrOrder:,:])).max()
    trans_sv = s[:pdnrOrder]
    trans_basis = v[:pdnrOrder, :]
    trans_stdevs = zeros((pdnrOrder + 1,), dtype=float)
    trans_stdevs[:-1] = sqrt(trans_sv / (nFrames * ntx * nNoiseConditions))
    trans_stdevs[-1] = sqrt(trans_noise_resid / (nFrames * ntx * nNoiseConditions))
    if reduceOrderForADNS:
        trans_noise_resid = dot(v[pdnrOrder-1:,:].T, dot(diag(s[pdnrOrder-1:]), v[pdnrOrder-1:,:])).max()
        trans_stdevs[-1] = sqrt(trans_noise_resid / (nFrames * ntx * nNoiseConditions))
        trans_stdevs[-2] = 0
        trans_basis[-1, :] *= 0

    if xTx_profx is not None:
        u, s, v = svd(xTx_profx)
        profx_noise_resid = dot(v[pdnrOrder:,:].T, dot(diag(s[pdnrOrder:]), v[pdnrOrder:,:])).max()
        profx_sv = s[:pdnrOrder]
        profx_basis = v[:pdnrOrder, :]
        profx_stdevs = zeros((pdnrOrder + 1,), dtype=float)
        profx_stdevs[:-1] = sqrt(profx_sv / (nFrames * nNoiseConditions))
        profx_stdevs[-1] = sqrt(profx_noise_resid / (nFrames * nNoiseConditions))
        if reduceOrderForADNS:
            profx_noise_resid = dot(v[pdnrOrder-1:,:].T, dot(diag(s[pdnrOrder-1:]), v[pdnrOrder-1:,:])).max()
            profx_stdevs[-1] = sqrt(profx_noise_resid / (nFrames * nNoiseConditions))
            profx_stdevs[-2] = 0
            profx_basis[-1, :] *= 0
    else:
        profx_basis = None
        profx_stdevs = None

    if xTx_profy is not None:
        u, s, v = svd(xTx_profy)
        profy_noise_resid = dot(v[pdnrOrder:,:].T, dot(diag(s[pdnrOrder:]), v[pdnrOrder:,:])).max()
        profy_sv = s[:pdnrOrder]
        profy_basis = v[:pdnrOrder, :]
        profy_stdevs = zeros((pdnrOrder + 1,), dtype=float)
        profy_stdevs[:-1] = sqrt(profy_sv / (nFrames * nNoiseConditions))
        profy_stdevs[-1] = sqrt(profy_noise_resid / (nFrames * nNoiseConditions))
        if reduceOrderForADNS:
            profy_noise_resid = dot(v[pdnrOrder-1:,:].T, dot(diag(s[pdnrOrder-1:]), v[pdnrOrder-1:,:])).max()
            profy_stdevs[-1] = sqrt(profy_noise_resid / (nFrames * nNoiseConditions))
            profy_stdevs[-2] = 0
            profy_basis[-1, :] *= 0
    else:
        profy_basis = None
        profy_stdevs = None

    tuning = constructTuning(config, trans_basis, trans_stdevs, profx_basis, profx_stdevs, profy_basis, profy_stdevs)

    return tuning

if __name__ == "__main__":
    set_printoptions(precision=2, linewidth=100)
    args = parse_args()
    config, frame_collections = parse_xml_log(args.noise_logfile)
    for collection_name, (im, px, py) in frame_collections.items():
        tuning = tunePDNR(config, im, px, py)
        for param_name, param_val in tuning.items():
            # Yuck, special case. pdnrConfigData is not part of the pdnrConfig struct; it's separate.
            if param_name == "pdnrConfigData":
                print("DS6Result:{} = {}".format(param_name, param_val))
            else:
                print("DS6Result:{}:{} = {}".format(collection_name, param_name, param_val))
