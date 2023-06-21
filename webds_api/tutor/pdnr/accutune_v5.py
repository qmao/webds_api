#!/usr/bin/env python3
# pdnr_tool Class for evaluating pdnr tuning results
#
# {
# Accutune Version 3
# Static functions:
#   tuneData() - process collections in data file(s)
#   selectData() - select input data to optimize tuning
# Example usage:
#   files[1] = 'C:\Users\Projects\pdnr\phone1_LP.xml'
#   files[2] = 'C:\Users\Projects\pdnr\phone2_LP.xml'
#   params, results = pdnr_tool.tuneData(files)
#   params, results = pdnr_tool.selectData(files)
# }
#                    COMPANY CONFIDENTIAL
#                     INTERNAL USE ONLY
#
# Copyright (C) 1997 - 2018  Synaptics Incorporated.
# All right reserved.
#
# This document contains information that is proprietary to Synaptics
# Incorporated. The holder of this document shall treat all information
# contained herein as confidential, shall use the information only for
# its intended purpose, and shall protect the information in whole or
# part from duplication, disclosure to any other party, or
# dissemination in any media without the written permission of
# Synaptics Incorporated.
#
# Synaptics Incorporated
# 1109 McKay Dr.
# San Jose, CA 95131
# (408) 904-1100
#

import copy
import json
import math
import os.path
import time
import warnings
from pathlib import Path
from typing import Any, Optional, Tuple, Union

import numpy as np
from scipy.linalg import svd
from scipy.signal import lfilter

from .ds6_xml import parse_xml_log
from .ds7_json import parse_json_data

CLIP_CHECK_EN = True

# classes to implement c-like structs
class File:
    def __init__(self):
        self.directory = None
        self.filename = None


class Params:
    def __init__(self):
        self.basisAmpStdevTransRx = np.array([])
        self.basisVectorsTransRx = np.array([])
        self.basisAmpStdevAbsRx = np.array([])
        self.basisVectorsAbsRx = np.array([])
        self.basisAmpStdevAbsTx = np.array([])
        self.basisVectorsAbsTx = np.array([])
        # self.TransStd = np.ndarray([])
        # self.AbsRxStd = np.ndarray([])
        # self.AbsTxStd = np.ndarray([])
        # self.TransBasis = np.ndarray([])
        # self.AbsRxBasis = np.ndarray([])
        # self.AbsTxBasis = np.ndarray([])
        # self.transOrderIter1 = 0
        # self.transResThFactor1 = 0
        # self.transResThFactor2 = 0
        # self.transResThFactor3 = 0
        # self.absRxResThFactor1 = 0
        # self.absRxResThFactor2 = 0
        # self.absTxResThFactor1 = 0
        # self.absTxResThFactor2 = 0

class Config(Params):
    def __init__(self, alt=0):
        if not alt:
            self.txCount = 0
            self.rxCount = 0
            self.nf = 0
            self.adnsEnabled = 0
            self.adnsEnable = 0
            self.saturationLevel = 0
            self.profileAmplitudeX = 0
            self.profileAmplitudeY = 0
            self.params = Params()
        else:
            self.nTx = 0
            self.Rx = 0
            self.nf = 0
            self.adnsEnable = 0
            self.nf = 0

class Frames:
    def __init__(self, trans=None, absRx=None, absTx=None):
        self.trans = trans
        self.absRx = absRx
        self.absTx = absTx


class Stats:
    def __init__(self):
        self.outlier = np.array([])
        self.augment = None
        self.trans = np.array([])
        self.absRx = np.array([])
        self.absTx = np.array([])


class Metrics:
    def __init__(self):
        self.peakRes = None
        self.rssMean = None
        self.rssStd = None


class Enables:
    def __init__(self):
        self.outlier = []


class Collections:
    def __init__(self):
        self.offsets = np.array([])
        self.nc = 0


class Subparams:
    def __init__(self):
        self.grammian = []
        self.nf = 0


class Freeze:
    def __init__(self):
        self.update = None
        self.index = None
        self.iterRange = None


class Results:
    def __init__(self):
        self.selection = []
        self.metric = []


class Dummy:
    def __init__(self):
        pass


class pdnr_tool(Config, Frames, Stats, File, Params, Metrics, Enables, Collections, Subparams, Freeze, Results, Dummy):

    # global parameters
    CLIP_CHECK_EN = True

    step = 0
    steps = 0
    params = None
    results = None

    def __repr__(self):
        return 'pdnr_tool'

    def __init__(self):
        # super().__init__()
        self.file = File()
        self.cfg = Config(alt=1)
        self.collection = Collections()
        self.mode = np.array([])
        self.indices = Frames()
        self.params = Params()
        self.tuning = Frames()
        self.delta = Frames(np.array([]), np.array([]), np.array([]))
        self.residual = Frames()
        self.outlier = Frames()
        self.augmentation = Frames([], [], [])
        self.metrics = Frames()
        self.enables = Enables()
        self.enables.outlier = 1
        self.dataset = None
        self.metadata = None
        self.offset = 750  # adns offset in basis calculation
        self.order = 4  # set to desired PDNR order
        self.stride = 1
        self.verbose = 1  # level of verbosity: 0:none, 1:text

    def loadData(self, file: str or dict) -> Optional[Tuple[int, Frames]]:
        """
        Loads data file raw frame collections and calculates delta frames
        Inputs:
            file = Path to file string
        Outputs:
            status = status flag
            raw = determined raw data frames
            Updates self.delta
        """

        # initialize
        if isinstance(file, str):
            self.file = File()
            self.file.directory, full_filename = os.path.split(file)
            self.file.filename, ext = os.path.splitext(full_filename)
        else:
            self.file.filename = file['filename']

        # parse and combine the raw data, then construct the config object
        if (isinstance(file, str) and Path(file).is_file()) or isinstance(file, dict):
            if self.verbose:
                print(' Parsing initiated on ' + self.file.filename + ' ')
            #self.metadata, self.dataset = parse_xml_log(file)  # data is parsed to a dict of 3-tuples( 3 subframes), containing ndarray data
            self.metadata, self.dataset = parse_json_data(file)
            nTx = self.metadata['txCount']
            nRx = self.metadata['rxCount']
            # determine the number of modes for pdnr config parameters
            num_modes = len([i for i in self.metadata.keys() if 'basisVectorsTransRx' in i])
            collection_names = list(self.dataset.keys())  # 'gears'
            trans = []
            absRx = []
            absTx = []
            collections = []
            # group all parsed data by subframe type and save the starting indices of each gear's data
            for n, i in enumerate(collection_names):
                trans = np.append(trans, self.dataset[i][0])
                absRx = np.append(absRx, self.dataset[i][1])
                absTx = np.append(absTx, self.dataset[i][2])
                collections.append(len(trans) // nTx // nRx - len(self.dataset[i][0]))  # NNN: empty gears not parsed, and thus not indexed!
            trans = trans.reshape((-1, nTx, nRx)).astype(int)
            absRx = absRx.reshape(-1, nRx).astype(int)
            absTx = absTx.reshape(-1, nTx).astype(int)
            collections = np.array(collections)

            # build config object
            config = Config()
            configs_of_interest = ['txCount', 'rxCount', 'nf', 'adnsEnabled', 'saturationLevel', 'profileAmplitudeX',
                                   'profileAmplitudeY', 'params']
            param_names = Params().__dict__.keys()
            for config_name in configs_of_interest:
                if config_name in self.metadata.keys():
                    setattr(config, config_name, self.metadata[config_name])
                elif config_name == 'nf':
                    config.nf = len(trans)
                elif config_name == 'params':
                    for mode in range(num_modes):  # NNN: usually only 1 mode (mode 0)?
                        nbv = len(self.metadata['ifpConfig.pdnrConfigs[{}].basisAmpStdevTransRx'.format(mode)]) - 1
                        [_, nTx, nRx] = np.shape(trans)
                        for param_name in param_names:
                            if 'AbsTx' in param_name:
                                multiplier = nTx
                            else:
                                multiplier = nRx
                            param_data = self.metadata['ifpConfig.pdnrConfigs[{}].'.format(mode) + param_name][:nbv * multiplier]
                            if 'basisVectors' in param_name:
                                param_data = np.array(param_data).reshape(-1, nbv)
                            setattr(config.params, param_name, np.array(param_data))
            if self.verbose:
                print(' Parsing done. Raw parsed data saved to "dataset" and "metadata" attributes')
        else:  # if file wasn't found
            print('Error: File not found: ' + file)
            return

        # append collections with the index of the last datapoint + 1 to set the end limit
        collections = np.append(collections, config.nf)

        # populate the top-level instance of Config
        self.cfg.nTx = config.txCount
        self.cfg.nRx = config.rxCount
        self.cfg.adnsEnable = config.adnsEnabled
        self.cfg.nf = config.nf
        self.cfg.cSat = config.saturationLevel
        if self.cfg.cSat == 0:
            self.cfg.cSat = 300

        # build instance collections
        self.collection = Collections()
        self.collection.offsets = -(- collections // self.stride)  # double negation to mimic MATLAB's ceil()
        self.cfg.nf = -(-config.nf // self.stride)
        self.collection.nc = len(self.collection.offsets)-1

        # strided raw data
        trans = trans[::self.stride, :, :]
        absRx = absRx[::self.stride, :]
        absTx = absTx[::self.stride, :]

        # delta data
        self.delta = Frames()
        self.delta.trans = np.array([]).reshape((0, nTx, nRx))
        self.delta.absRx = np.array([]).reshape(0, nRx)
        self.delta.absTx = np.array([]).reshape(0, nTx)
        # calculate and combine deltas for all collections into one delta object
        for i in range(self.collection.nc):
            # set collection indices
            if self.collection.nc <= 1:
                inds = np.arange(self.cfg.nf)
            else:
                inds = np.arange(self.collection.offsets[i], self.collection.offsets[i + 1])
            # initialize
            raw = Frames()
            delta = Frames()
            # set collection raw frames
            if trans.any():
                raw.trans = trans[inds, :, :]
            if absRx.any():
                raw.absRx = absRx[inds, :]
            if absTx.any():
                raw.absTx = absTx[inds, :]
            offset = 0  # deltas are calculated and saved w/o offset
            verbose = 0
            # calculate and set collection delta frames
            delta.trans, delta.absRx, delta.absTx = self.calcDelta(raw.trans, raw.absRx, raw.absTx, offset, verbose)
            self.delta.trans = np.concatenate((self.delta.trans, delta.trans), axis=0)
            self.delta.absRx = np.concatenate((self.delta.absRx, delta.absRx))
            self.delta.absTx = np.concatenate((self.delta.absTx, delta.absTx))

        # initialize tuning
        self.tuning = Frames()

        # initialize mode
        if self.collection.nc > 0:
            self.initMode(-1)  # -1 := all collections
            if self.verbose:
                print('   Initialized to all collections.')

        # outputs
        status = 1
        for subframe in ['trans', 'absRx', 'absTx']: # raw.trans ,raw.abs
            setattr(raw, subframe, locals()[subframe])

        return status, raw

    # end loadData()-------------------------------------------------------------

    def initMode(self, collection_mode=-1):
        """
        Reset states or tuning, outlier  and set data indices for selected collection
        Inputs:
            collection_mode: zero-based collection number
        Outputs:
            Updates self.mode and self.indices,
            Resets object's tuning outlier and augmentation attributes
        """

        # error check
        if not self.collection.nc:
            print("\nWarning: No collections detected. Aborting initialization.")
            return

        # set collection indices
        if collection_mode == -1 or self.collection.nc == 1:
            inds = np.arange(self.cfg.nf)
        else:
            collection_mode = min(collection_mode, self.collection.nc - 1)  # collection mode is zero based
            inds = np.arange(self.collection.offsets[collection_mode], self.collection.offsets[collection_mode + 1])

        self.indices = Frames()
        for subframe in ['trans', 'absRx', 'absTx']:
            if getattr(self.delta, subframe).any():
                setattr(self.indices, subframe, copy.deepcopy(inds))

        # reinitialize tuning
        self.tuning = Frames()

        # reinitialize data outlier indices
        self.outlier = Frames()

        #  reinitialize data augmentation indices
        self.augmentation = Frames([], [], [])

        # set mode
        self.mode = collection_mode

    # end initMode()_________________________________________________

    def tune(self, augment=False):
        """
        Tune params based on a single pdnr_tool object by calling calcParams().
        Inputs:
            augment = enable/disable augmentation
        Outputs:
            Returns nothing, but updates self.params
        """

        # initialize
        if not self.tuning.trans:
            indicesTrans = self.indices.trans
        else:
            indicesTrans = []
        if not self.tuning.absRx:
            indicesAbsRx = self.indices.absRx
        else:
            indicesAbsRx = []
        if not self.tuning.absTx:
            indicesAbsTx = self.indices.absTx
        else:
            indicesAbsTx = []

        # data augmentation
        if augment:
            # Note: augmented indices are wrt the selected mode's indices (starts at 0)
            indicesTrans = np.append(indicesTrans, self.indices.trans[self.augmentation.trans]).astype(int)
            indicesAbsRx = np.append(indicesAbsRx, self.indices.absRx[self.augmentation.absRx]).astype(int)
            indicesAbsTx = np.append(indicesAbsTx, self.indices.absTx[self.augmentation.absTx]).astype(int)

        # extract deltas
        trans = self.delta.trans[indicesTrans, :, :]
        absRx = self.delta.absRx[indicesAbsRx, :]
        absTx = self.delta.absTx[indicesAbsTx, :]

        # offset deltas
        if self.cfg.adnsEnable:
            trans = trans + self.offset
            absRx = absRx - self.offset
            absTx = absTx - self.offset

        # tune using offset deltas
        self.params = self.calcParams(trans, absRx, absTx, self.order, self.verbose == 1)

    # end tune()___________________________________________________________________

    def tuneDeltas(self, pts, augment=False, augment_pts=False):
        """
        Tune params based on multiple pdnr_tool objects
        Inputs:
            pts = cell array of pdnr_tool objects
            augment = conglomerate augmentation enable
            augment_pts = individual pts augmentation enable
        Outputs:
            Updates self.params
        """
        # data size
        npts = len(pts)
        if npts == 0:
            print('   Tune aborted. No data available')
            return

        # update frame indices offsets
        if augment_pts:
            ptsOffsets = Frames([0], [0], [0])
            for i in range(npts):
                ptsOffsets.trans.append(ptsOffsets.trans[i] + len(pts[i].indices.trans))
                ptsOffsets.absRx.append(ptsOffsets.absRx[i] + len(pts[i].indices.absRx))
                ptsOffsets.absTx.append(ptsOffsets.absTx[i] + len(pts[i].indices.absTx))

        # concatenate frames not already stored for tuning
        if not self.tuning.trans:
            self.delta.trans = np.array([]).reshape((0, pts[0].cfg.nTx, pts[0].cfg.nRx))
            for i in range(npts):
                self.delta.trans = np.concatenate((self.delta.trans, pts[i].delta.trans[pts[i].indices.trans, :, :]),
                                                  axis=0)  # deltas contain only for the selected mode(s)
            s = np.shape(self.delta.trans)
            self.indices.trans = np.arange(s[0])
        if not self.tuning.absRx:
            self.delta.absRx = np.array([]).reshape(0, pts[0].cfg.nRx)
            for i in range(npts):
                self.delta.absRx = np.concatenate((self.delta.absRx, pts[i].delta.absRx[pts[i].indices.absRx, :]), axis=0)
            self.indices.absRx = np.arange(np.shape(self.delta.absRx)[0])
        if not self.tuning.absTx:
            self.delta.absTx = np.array([]).reshape(0, pts[0].cfg.nTx)
            for i in range(npts):
                self.delta.absTx = np.concatenate((self.delta.absTx, pts[i].delta.absTx[pts[i].indices.absTx, :]), axis=0)
            self.indices.absTx = np.arange(np.shape(self.delta.absTx)[0])

        # initialize
        self.cfg = copy.deepcopy(pts[0].cfg)
        self.cfg.nf = len(self.indices.trans)
        self.offset = copy.deepcopy(pts[0].offset)

        # calculate indices for fit
        if not self.tuning.trans:
            indicesTrans = self.indices.trans
        else:
            indicesTrans = []
        if not self.tuning.absRx:
            indicesAbsRx = self.indices.absRx
        else:
            indicesAbsRx = []
        if not self.tuning.absTx:
            indicesAbsTx = self.indices.absTx
        else:
            indicesAbsTx = []

        # data augmentation
        if augment:
            # augmented indices are wrt the selected mode's indice frame (starts at 0)
            indicesTrans = np.append(indicesTrans, self.indices.trans[self.augmentation.trans]).astype(int)
            indicesAbsRx = np.append(indicesAbsRx, self.indices.absRx[self.augmentation.absRx]).astype(int)
            indicesAbsTx = np.append(indicesAbsTx, self.indices.absTx[self.augmentation.absTx]).astype(int)

        # pts data augmentation
        if augment_pts:
            # augmented indices are wrt the selected mode's indice frame (starts at 0)
            for i in range(npts):
                indicesTrans = np.append(indicesTrans, ptsOffsets.trans[i] + pts[i].indices.trans[pts[i].augmentation.trans])
                indicesAbsRx = np.append(indicesAbsRx, ptsOffsets.absRx[i] + pts[i].indices.absRx[pts[i].augmentation.absRx])
                indicesAbsTx = np.append(indicesAbsTx, ptsOffsets.absTx[i] + pts[i].indices.absTx[pts[i].augmentation.absTx])

        # extract deltas
        trans = self.delta.trans[indicesTrans, :, :]
        absRx = self.delta.absRx[indicesAbsRx, :]
        absTx = self.delta.absTx[indicesAbsTx, :]

        # offset deltas
        if self.cfg.adnsEnable:
            trans = trans + self.offset
            absRx = absRx - self.offset
            absTx = absTx - self.offset

        # tune using offset deltas
        self.params = self.calcParams(trans, absRx, absTx, self.order, self.verbose == 1)

    # end tuneDeltas()_________________________________________________________________________

    def fit(self, nsd=8):
        """
        Fit all subframes, calculating residual error
        Inputs:
            nsd = number of standard deviations to use for data augmentation threshold
        """
        if self.delta.trans.any():
            self.fitTrans(nsd)
        # fit absRx
        if self.delta.absRx.any():
            self.fitAbsRx(nsd)
        # fit absTx
        if self.delta.absTx.any():
            self.fitAbsTx(nsd)

    def fitTrans(self, nsd=8, bv=None):
        """
        Set up to fit trans subframe using fitImages() to calculate residual error.
        nsd = number of standard deviations to use for data augmentation threshold
        bv = matrix of basis vector numerical values
        Updates: object's trans residuals 'self.residual.trans'
        """
        # error check and defaults
        if bv is None:
            bv = []
        if not self.delta.trans.any():
            print("   Trans delta frames missing. Need to call loadData() first.")
            return
        if not bv:
            if not self.params:
                print('   Trans params missing. Need to call tune() first.')
                return
            else:
                bv = self.params.basisVectorsTransRx.astype(float) / 2 ** 15

        # fit trans using selected indices
        self.residual.trans = self.fitImages(self.delta.trans[self.indices.trans, :, :], nsd, bv, 'Trans')

    # end fit()________________________________________________________________

    def fitAbsRx(self, nsd=8, bv=None):
        """
        Set up to fit absRx subframe using fitClusters() to calculate residual error
        nsd = number of standard deviations to use for data augmentation threshold
        bv = matrix of basis vector numerical values
        Updates: object's trans residuals 'self.residual.trans
        """
        # error checking and defaults
        if bv is None:
            bv = []
        if not self.delta.absRx.any():
            if len(self.delta.absTx) == 0:
                raise ValueError('   Delta frames missing (AbsTx).  Need to call tune() first.')
            else:
                warnings.warn("Warning: All data entries are zero, check for clipping")
        if bv is None or len(bv) == 0:
            bv = self.params.basisVectorsAbsRx.astype(float) / 2 ** 15
        # fit subset of abs frames defined by by self.indices
        self.residual.absRx = self.fitClusters(self.delta.absRx[self.indices.absRx, :], nsd, bv, 'AbsRx')

    # end fitTrans()_____________________________________________________________
    def fitAbsTx(self, nsd=8, bv=None):
        """
        Set up to fit absTx subframe using fitClusters() to calculate residual error
        nsd = number of standard deviations to use for data augmentation threshold
        bv = matrix of basis vector numerical values
        Updates: object's trans residuals 'self.residual.trans
        """
        # error checking and defaults
        if bv is None:
            bv = []
        if not self.delta.absTx.any():
            if len(self.delta.absTx) == 0:
                raise ValueError('   Delta frames missing (AbsTx).  Need to call tune() first.')
            else:
                warnings.warn("Warning: All data entries are zero, check for clipping")
        if bv is None or len(bv) == 0:
            bv = self.params.basisVectorsAbsTx.astype(float) / 2 ** 15
        # fit
        self.residual.absTx = self.fitClusters(self.delta.absTx[self.indices.absTx, :], nsd, bv, 'AbsTx')

    # end fitAbsRx()_____________________________________________________________
    def augment(self, nsd=3, num_iter=200, pts=None):
        """
        Tune each subframe using augmented data
        Inputs:
            nsd = number of standard deviations to use for data augmentation threshold
            iter = maximum number of iterations
            pts = list of pdnr_tool objects
        Outputs:
            Updates self.params
        """
        # defaults
        if pts is None:
            pts = []
        if isinstance(num_iter, int):  # if len(iter) == 1
            num_iter = np.kron(np.ones(3, dtype=int), num_iter)

        # augment each subframe
        for i, subframe in enumerate(['Trans', 'AbsRx', 'AbsTx']):
            self.augmentData(subframe, nsd, num_iter[i], pts)

    # end fitAbsTx()_____________________________________________________________

    def calcParams(self, deltaTrans: np.ndarray, deltaAbsRx: np.ndarray, deltaAbsTx: np.ndarray, order: int, verbose: int) -> Optional[Params]:
        """
        Calculate PDNR configuration parameters using all subframes deltas
        Inputs:
            deltaXxx = subframe deltas
            order = PDNR order
            verbose = set to 1 for text output
        Outputs:
            Returns PDNR parameters 'params'
            Updates self.tuning, containing grammians and number of frames 'nf'
        """

        # error check
        if not (deltaTrans.any() or deltaAbsRx.any() or deltaAbsTx.any() or self.tuning.trans or self.tuning.absRx or self.tuning.absTx):
            print('Tuning aborted. Delta frames not set')
            params = self.params
            return

        # initialize parameters
        basisNumFracBits = 15
        params = Params()

        # trans
        if deltaTrans.any() or self.tuning.trans:
            nf = np.shape(deltaTrans)[0]
            temp = deltaTrans.reshape((-1, deltaTrans.shape[2]))
            imgf = temp.T @ temp

            if not self.tuning.trans:
                self.tuning.trans = Subparams()
                self.tuning.trans.grammian = imgf
                self.tuning.trans.nf = nf
            else:
                imgf = imgf + self.tuning.trans.grammian
                nf = nf + self.tuning.trans.nf

            # set basis
            _, s, v = svd(imgf, lapack_driver='gesvd')
            v = v.T
            sv = s / np.size(deltaTrans, 1) / nf
            for i in range(len(sv)):
                if (sv[i] - sv[i + 1]) / sv[i] < 0.2:
                    i = max(1, i - 1)
                    break
            if not order:
                order = max(2, min(4, i))
            if verbose:
                print('Basis order set to {}\n'.format(order))
                print('Recommended trans basis order range is from {} to {}'.format(i + 1, i + 2))

            stdr = np.max(np.sqrt(np.diag(v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T)))  # Last element is standard deviation of the residual
            params.basisAmpStdevTransRx = [np.sqrt(sv[i]) for i in range(order)] + [stdr]
            params.residualCovarianceTransRx = v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T
            params.basisVectorsTransRx = (2 ** basisNumFracBits * v[:, :order]).round().astype(np.int16).reshape(-1, order)
            params.TransStd = np.sqrt(sv[:])
            params.TransBasis = v

        # absRx
        if deltaAbsRx.any() or self.tuning.absRx:
            nf = np.shape(deltaAbsRx)[0]
            temp = deltaAbsRx.reshape((-1, deltaAbsRx.shape[1]))
            absrxf = temp.T @ temp
            if not self.tuning.absRx:
                self.tuning.absRx = Subparams()
                self.tuning.absRx.grammian = absrxf
                self.tuning.absRx.nf = nf
            else:
                absrxf = absrxf + self.tuning.absRx.grammian
                nf = nf + self.tuning.absRx.nf

            # set basis
            _, s, v = svd(absrxf, lapack_driver='gesvd')
            v = v.T
            sv = s / nf
            for i in range(len(sv)):
                if (sv[i] - sv[i + 1]) / sv[i] < 0.2:
                    i = max(1, i - 1)
                    break
            if not order:
                order = max(2, min(4, i))
            if verbose:
                print('Basis order set to {}'.format(order))
                print('Recommended abs rx basis order range is from {} to {}'.format(i + 1, i + 2))

            stdr = np.max(np.sqrt(np.diag(v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T)))
            params.basisAmpStdevAbsRx = [np.sqrt(sv[i]) for i in range(order)] + [stdr]  # Last element (stdr) is standard deviation of the residual
            params.residualCovarianceAbsRx = v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T
            params.basisVectorsAbsRx = (2 ** basisNumFracBits * v[:, :order]).round().astype(np.int16).reshape(-1, order)
            params.AbsRxStd = np.sqrt(sv[:])
            params.AbsRxBasis = v

        # absTx
        if deltaAbsTx.any() or self.tuning.absTx:
            nf = np.shape(deltaAbsTx)[0]
            temp = deltaAbsTx.reshape((-1, deltaAbsTx.shape[1]))
            absrxf = temp.T @ temp
            if not self.tuning.absTx:
                self.tuning.absTx = Subparams()
                self.tuning.absTx.grammian = absrxf
                self.tuning.absTx.nf = nf
            else:
                absrxf = absrxf + self.tuning.absTx.grammian
                nf = nf + self.tuning.absTx.nf

            # set basis
            _, s, v = svd(absrxf, lapack_driver='gesvd')
            v = v.T
            sv = s / nf
            for i in range(len(sv)):
                if (sv[i] - sv[i + 1]) / sv[i] < 0.2:
                    i = max(1, i - 1)
                    break
            if not order:
                order = max(2, min(4, i))
            if verbose:
                print('Basis order set to {}'.format(order))
                print('Recommended abs rx basis order range is from {} to {}'.format(i + 1, i + 2))

            stdr = np.max(np.sqrt(np.diag(v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T)))
            params.basisAmpStdevAbsTx = [np.sqrt(sv[i]) for i in range(order)] + [stdr]  # Last element (stdr) is standard deviation of the residual
            params.residualCovarianceAbsTx = v[:, order:] @ np.diag(sv[order:]) @ v[:, order:].T
            params.basisVectorsAbsTx = (2 ** basisNumFracBits * v[:, :order]).round().astype(np.int16).reshape(-1, order)
            params.AbsTxStd = np.sqrt(sv[:])
            params.AbsTxBasis = v

        return params

    # end augment()________________________________________________________________

    def augmentTrans(self, nsd=3, iter=200, pts=None):
        """
        Tune using augmented data
        Inputs:
            nsd = number of standard deviations to use for data augmentation threshold
            iter = maximum number of iterations
            pts = list of pdnr_tool objects
        Outputs:
            Updates self.params
        """
        if pts is None:
            pts = []

        self.augmentData('Trans', nsd, iter, pts)

    # end augmentTrans()________________________________________________________

    def augmentAbsRx(self, nsd=3, iter=200, pts=None):
        """
        Tune using augmented data
        Inputs:
            nsd = number of standard deviations to use for data augmentation threshold
            iter = maximum number of iterations
            pts = list of pdnr_tool objects
        Outputs:
            Updates self.params
        """
        if pts is None:
            pts = []

        self.augmentData('AbsRx', nsd, iter, pts)

    # end augmentAbsRx()________________________________________________________

    def augmentAbsTx(self, nsd=3, iter=200, pts=None):
        """
        Tune using augmented data
        Inputs:
            nsd = number of standard deviations to use for data augmentation threshold
            iter = maximum number of iterations
            pts = list of pdnr_tool objects
        Outputs:
            Updates self.params
        """
        if pts is None:
            pts = []

        self.augmentData('AbsTx', nsd, iter, pts)

    # end augmentAbsTx()________________________________________________________

    def getBasis(self):
        """ Accessor for numerical representation of basis vectors """

        bvTrans = (self.params.basisVectorsTransRx).astype(float) / 2 ** 15
        bvAbsRx = (self.params.basisVectorsAbsRx).astype(float) / 2 ** 15
        bvAbsTx = (self.params.basisVectorsAbsTx).astype(float) / 2 ** 15

        return bvTrans, bvAbsRx, bvAbsTx

    # end getBasis()__________________________________________________________

    def getParams(self):
        """ Accessor for structure of pdnr parameter values """

        params = self.params
        return params

    # end getParams()__________________________________________________________
    # end of public methods

    # Private methods__________________________________________________________

    def outliers(self, residuals, name, nsd=4):
        """
        # checks for data outliers
        # residuals = matrix of residuals
        # name = subframe name
        # nsd = number of standard deviations to use for outlier threshold

        # assume a chi-squared distribution for cluster residuals
        # check to see if any cluster response is an outlier by
        # checking the Mahalanobis distance
        """

        if name == 'Trans':
            nf, ntx, nrx = np.shape(residuals)
            m = np.mean(residuals, axis=0)
            sd = np.std(residuals, axis=0)
            self.outlier.trans = np.array([])
            for i in range(nf):
                if (np.sqrt(np.sum((residuals[i, :, :] - m) ** 2 / sd ** 2, 1)) / nrx >= nsd).any():
                    self.outlier.trans = np.append(self.outlier.trans, i).astype(int)
            # display results
            if self.verbose:
                if self.outlier.trans:
                    print('\n   Trans outlier(s) detected at following frame(s):')
                    print(*self.outlier.trans, sep=',')
        if name == 'AbsRx':
            nf, nrx = np.shape(residuals)
            m = np.mean(residuals, axis=0)
            sd = np.std(residuals, axis=0)
            self.outlier.absRx = np.array([])
            for i in range(nf):
                if (np.sqrt(np.sum((residuals[i, :] - m) ** 2 / sd ** 2)) / nrx >= nsd).any():
                    self.outlier.absRx = np.append(self.outlier.absRx, i).astype(int)
            # display results
            if self.verbose:
                if self.outlier.absRx:
                    print('\n   AbsRx outlier(s) detected at following frame(s):')
                    print(*self.outlier.absRx, sep=',')
        if name == 'AbsTx':
            nf, ntx = np.shape(residuals)
            m = np.mean(residuals, axis=0)
            sd = np.std(residuals, axis=0)
            self.outlier.absTx = np.array([])
            for i in range(nf):
                if (np.sqrt(np.sum((residuals[i, :] - m) ** 2 / sd ** 2)) / ntx >= nsd).any():
                    self.outlier.absTx = np.append(self.outlier.absTx, i).astype(int)
            # display results
            if self.verbose:
                if self.outlier.absTx:
                    print('\n   AbsTx outlier(s) detected at following frame(s):')
                    print(*self.outlier.absTx, sep=',')

    # end outliers()__________________________________________________________________

    def fitImages(self, delta: np.ndarray, nsd: int, bvs: np.ndarray, name: str) -> np.ndarray:
        """
        Fits images and calculates residuals
        Inputs:
            delta = matrix of delta subframes nf x nTx x nRx
            nsd = number of standard deviations to use for augmentation threshold
            bvs = matrix of basis vectors of shape self.nRx x self.order
            name str = subframe name
        Outputs:
            Returns residuals
            Updates outlier indices in 'self.augmentation.trans'
            Updates metrics (Peak Residual Error, RSS Mean and RSS std in 'self.metrics.trans'
        """

        # initialize
        nf, ntx, nrx = np.shape(delta)
        residual = np.zeros((nf, ntx, nrx))  # corrected profiles (i.e. removed interference)
        nm = name
        nm = nm[0].lower() + nm[1:]

        # fit, residual and errors
        err = np.zeros(nf)
        for i in range(nf):
            d = delta[i, :, :]
            w = bvs.T @ d.T
            residual[i, :, :] = d - (bvs @ w).T
            # max RSS error (2 norm)
            err[i] = np.max(np.sqrt(np.sum(residual[i, :, :] ** 2, 1)))  # sum over clusters (Rx'es)

        self.metrics.trans = Metrics()
        self.metrics.trans.peakRes = abs(residual).max()
        self.metrics.trans.rssMean = np.mean(err)
        self.metrics.trans.rssStd = np.std(err)

        if self.verbose:
            print('\n   Trans Residual Errors (ADC):')
            print('   Peak Err\tRSS Std')
            print('   {:8.4f}\t{:7.4f}'.format(self.metrics.trans.peakRes, self.metrics.trans.rssStd))

        # check for outliers in residual
        if self.enables.outlier:
            self.outliers(residual, name, 4)

        # augmentation
        # note: it appears empirically that augmenting based on the normal
        #       distribution approximation is faster than the chi squared
        #       and produces equivalent results
        thresh = self.metrics.trans.rssMean + nsd * self.metrics.trans.rssStd
        augment = [i > thresh for i in err]  # RSS is always non-negative
        ind = [i for i, x in enumerate(augment) if x]  # find all indices where True
        if self.enables.outlier:
            ind = sorted(set(ind) - set(getattr(self.outlier, nm)))  # select non-outliers
        setattr(self.augmentation, nm, np.concatenate((getattr(self.augmentation, nm), ind)).astype(int))  # add to augmentation list

        return residual.astype(np.float32)  # return as 32-bit floats to save memory with minimal effect on error

    # end fitImages()___________________________________________________________________

    def fitClusters(self, delta: np.ndarray, nsd: int, bvs: np.ndarray, name: str) -> np.ndarray:
        """
        Fits clusters and calculates residuals
        Inputs:
            delta = matrix of delta subframes nf x nTx x nRx
            nsd = number of standard deviations to use for augmentation threshold
            bvs = matrix of basis vectors of shape self.nRx x self.order
            name str = subframe name
        Outputs:
            Returns residuals
            Updates outlier indices in 'self.augmentation.<subframe_name>'
            Updates metrics (Peak Residual Error, RSS Mean and RSS std in 'self.metrics.<subframe_name>'
        """

        # initialize
        # ne, nf = np.shape(delta)
        nm = name
        nm = nm[0].lower() + nm[1:]  # stats structure field name
        # fit and residual
        w = bvs.T @ delta.T
        residual = delta - (bvs @ w).T
        # RSS error (2 norm)
        setattr(self.metrics, nm, Metrics())
        getattr(self.metrics, nm).peakRes = abs(residual).max()
        err = np.sqrt(np.sum(residual ** 2, axis=1))
        getattr(self.metrics, nm).rssMean = np.mean(err)
        getattr(self.metrics, nm).rssStd = np.std(err)
        if self.verbose:
            print('\n  ' + name + 'Residual Errors (ADC):')
            print('   Peak Err\tRSS Std')
            print('   {:8.4f}\t{:7.4f}'.format(getattr(self.metrics, nm).peakRes, getattr(self.metrics, nm).rssStd))

        # check for outliers in residual
        if self.enables.outlier:
            self.outliers(residual, name, 4)

        # augmentation
        # note: it appears empirically that augmenting based on the normal
        #       distribution approximation is faster than the chi squared
        #       and produces equivalent results
        normalAugmentation = True
        if normalAugmentation:
            # augmentation - based on normal distribution approximation for RSS
            thresh = getattr(self.metrics, nm).rssMean + nsd * getattr(self.metrics, nm).rssStd
            augment = [i > thresh for i in err]  # RSS is always non-negative
        else:
            # augmentation - based on multivariate chi squared distribution
            x = np.sum((residual - np.mean(residual, 0)) ** 2 / np.std(residual, axis=0) ** 2, axis=1)
            thresh = np.mean(x) + nsd * np.std(x, ddof=1)  # ddof=1 -> sample std
            augment = [i > thresh for i in x]

        ind = np.array([i for i, x in enumerate(augment) if x])  # find augmentation indices
        if self.enables.outlier:
            ind = sorted(set(ind) - set(getattr(self.outlier, nm)))  # setdiff()
        setattr(self.augmentation, nm, np.concatenate((getattr(self.augmentation, nm), ind)).astype(int))

        return residual.astype(np.float32)  # return as 32-bit floats to save memory with minimal effect on error

    # end fitClusters()_________________________________________________________________

    def augmentData(self, name, nsd, iter=200, pts=None):
        """
        Tune chosen subframe using augmented data
        Inputs:
            name = subframe name - 'Trans', 'AbsRx', or 'AbsTx'
            nsd = number of standard deviations to use for data augmentation threshold
            iter = maximum number of iterations
            pts = array of pdnr_tool objects (used for tuning deltas)
        Outputs:
            Updates self.params and augmentation indices in self.augmentation
        Notes:
        Augmentation indices are only used in tune() to calculate the config parameters and
        updated and stored in fitXxxx() for a subsequent call to tune().
        In searching for the minimum peak and RSS errors, fitXxxx() will necessarily overstep the minimum.
        A two sample delay of augmentation indices is required to return the indices to those used to
        create the minimum errors (assuming at least 2 iterations have occurred).
        """
        # defaults
        if pts is None:
            pts = []
        # set data structure field names
        nm = name[0].lower() + name[1:]

        # check
        if not getattr(self.delta, nm).any():
            if not pts:
                return
            # check pts deltas
            non_empty = 0
            for p in pts:
                if getattr(p.delta, nm).any():  # assumes we never get all-zero deltas
                    non_empty = 1
                    break
            if not non_empty:
                return

        # disable verbosity
        priorVerbose = self.verbose
        self.verbose = 0

        # tuning
        params = copy.deepcopy(self.params)  # save existing params
        setattr(self.augmentation, nm, [])  # ensure initially empty indices
        augment1 = []  # one delay augmentation list
        if not pts:
            self.tune()  # tune without augmentation
        else:
            self.tuning = Frames()  # initialize tuning
            self.tuneDeltas(pts)  # tune without augmentation

        # fit
        eval('self.fit' + name + '(' + str(nsd) + ', [])')  # fit and update augmentation indices (for next call to tune(augment=True))
        errs = [getattr(self.metrics, nm).peakRes, getattr(self.metrics, nm).rssStd]
        # augmentation
        if getattr(self.augmentation, nm).any():  # if augmentation indices are defined for current subframe
            if priorVerbose:
                print(['\n   ' + name + ' Augmentation:'])
                print('   Iter  Peak Err  RSS Std')
                print('   {:4d}  {:8.4f}  {:7.4f}'.format(0, getattr(self.metrics, nm).peakRes, getattr(self.metrics, nm).rssStd))
            # initialize local minimum search parameters
            freeze = Freeze()
            freeze.update = 0  # enable to freeze iteration update
            freeze.index = 0  # iteration index of last local minimum
            freeze.iterRange = 5  # number of iterations in local minimum search

            # iterate
            for i in range(iter):
                if not freeze.update:
                    metrics = copy.deepcopy(getattr(self.metrics, nm))
                    augment2 = copy.deepcopy(augment1)  # two delay augmentation list
                augment1 = getattr(self.augmentation, nm)
                if not len(pts) > 0:
                    self.tune(augment=True)  # tune with augmentation
                else:
                    self.tuneDeltas(pts, augment=True)  # tune with augmentation
                eval('self.fit' + name + '(' + str(nsd) + ', [])')  # call fit on the current subframe
                errs = np.vstack((errs, [getattr(self.metrics, nm).peakRes, getattr(self.metrics, nm).rssStd]))
                if getattr(self.metrics, nm).peakRes < metrics.peakRes:
                    if priorVerbose:
                        print('   {:4d} {:8.4f} {:7.4f}', i, getattr(self.metrics, nm).peakRes, getattr(self.metrics, nm).rssStd)
                    freeze.update = 0
                    freeze.index = i + 1
                else:
                    # only check an initial descent - little return vs computational time after that
                    if i < 19 and i < freeze.index + freeze.iterRange:
                        # check to see if a more global minimum exists beyond:
                        if not freeze.update:
                            freeze.index = i
                            freeze.update = 1
                    else:
                        break
            errs = errs[:freeze.index + 1, :]
            if i == iter:
                # update augmentation list
                if not freeze.update:
                    metrics = getattr(self.metrics, nm)
                    augment2 = copy.deepcopy(augment1)  # two delay augmentation list
                if priorVerbose:
                    print('   Iterations maxed at {}.'.format(iter))
            # check for minimal movement
            if freeze.index > 0:
                atten = errs[0][0] - errs[-1][0]
                min_atten = 1  # require at least 1 LSB count
                if atten < min_atten or atten < 3 * (errs[-1][1] - errs[0][1]):
                    # reset to un-augmented tuning
                    augment2 = []
                    errs = np.vstack((errs, errs[0][:]))
                    if priorVerbose:
                        print('   {:4d} {:8.4f} {:7.4f}'.format(0, errs[0][0], errs[0][1]))
            # restore prior augmentation settings
            setattr(self.augmentation, nm, augment2)
            if not len(pts) > 0:
                self.tune(augment=True)
            else:
                self.tuneDeltas(pts, augment=True)
            eval('self.fit' + name + '(np.inf, [])')  # calculate min error fit

        # update subframe data parameters
        if params:
            if nm == 'trans':
                params.basisAmpStdevTransRx = self.params.basisAmpStdevTransRx
                params.basisVectorsTransRx = self.params.basisVectorsTransRx
                params.TransStd = self.params.TransStd
                params.TransBasis = self.params.TransBasis
                params.residualCovarianceTransRx = self.params.residualCovarianceTransRx
            if nm == 'absRx':
                params.basisAmpStdevAbsRx = self.params.basisAmpStdevAbsRx
                params.basisVectorsAbsRx = self.params.basisVectorsAbsRx
                params.AbsRxStd = self.params.AbsRxStd
                params.AbsRxBasis = self.params.AbsRxBasis
                params.residualCovarianceAbsRx = self.params.residualCovarianceAbsRx
            if nm == 'absTx':
                params.basisAmpStdevAbsTx = self.params.basisAmpStdevAbsTx
                params.basisVectorsAbsTx = self.params.basisVectorsAbsTx
                params.AbsTxStd = self.params.AbsTxStd
                params.AbsTxBasis = self.params.AbsTxBasis
                params.residualCovarianceAbsTx = self.params.residualCovarianceAbsTx
            self.params = params

        # restore verbose mode
        self.verbose = priorVerbose

    # end augmentData()_________________________________________________________________

    def removeOutliers(self, disableEvalOrder=0):
        """ Remove outlier frames and re-tune and re-fit remaining frames """

        # calculate superset of all outlier frames
        global offset
        ind = list(set().union(self.outlier.absRx, self.outlier.absTx, self.outlier.trans))

        # remove outlier frames
        if ind:
            # update number of frames
            self.cfg.nf = self.cfg.nf - len(ind)

            # calculate offset
            if self.mode < 0:
                offset = 0
            else:
                offset = self.collection.offsets[self.mode]

            # update deltas
            if self.indices.trans.size > 0:
                self.delta.trans = np.delete(self.delta.trans, ind + offset, 0)
            if self.indices.absRx.size > 0:
                self.delta.absRx = np.delete(self.delta.absRx, ind + offset, 0)
            if self.indices.absTx.size > 0:
                self.delta.absTx = np.delete(self.delta.absTx, ind + offset, 0)

            # remove outlier frames
            ind0 = copy.deepcopy(ind)
            for i in range(len(ind)):
                # update indices
                if self.indices.trans.size > 0:
                    self.indices.trans = np.concatenate((self.indices.trans[: ind0[i]], self.indices.trans[ind0[i] + 1:] - 1))
                if self.indices.absRx.size > 0:
                    self.indices.absRx = np.concatenate((self.indices.absRx[: ind0[i]], self.indices.absRx[ind0[i] + 1:] - 1))
                if self.indices.absTx.size > 0:
                    self.indices.absTx = np.concatenate((self.indices.absTx[: ind0[i]], self.indices.absTx[ind0[i] + 1:] - 1))
                # update collection offsets
                self.collection.offsets[self.collection.offsets > ind0[i]] = self.collection.offsets[self.collection.offsets > ind0[i]]-1
                # update outlier indices
                ind0[i + 1:] = [x - 1 for x in ind0[i + 1:]]

            # re-instantiate tuning
            self.tuning = Frames()
            # re-instantiate data outlier indices
            self.outlier = Frames()
            # re-instantiate data augmentation indices
            self.augmentation = Frames([], [], [])

        # display results
        if self.verbose:
            if not ind:
                print('\n   No outliers found.')
            else:
                if not disableEvalOrder:
                    print('\n   Calling tune(), evalOrder(), and fit() to update tuning, fit, and errors sans outliers.')
                else:
                    print('\n   Calling tune() and fit() to update tuning, fit, and errors sans outliers.')

        # update tuning, fit, and peak error vs order
        if ind:
            if self.verbose:
                print('\n   Outlier(s) removed at following frame(s):', *(ind + offset))
            self.tune()  # call after eliminating outliers to recompute config params
            if not disableEvalOrder:
                self.evalOrder()  # calculate residual peak errors vs order
            self.fit()  # fit all frames

    def evalOrder(self, retune=0):
        """ Evaluates peak error vs order """

        # initialize
        maxOrder = 2 * self.order
        ind = np.arange(1, maxOrder + 1)

        # disable verbosity
        priorVerbose = self.verbose
        self.verbose = 0

        # reinitialize tuning
        self.tuning = Frames()

        # calculate indices for fit
        indicesTrans = self.indices.trans
        indicesAbsRx = self.indices.absRx
        indicesAbsTx = self.indices.absTx


        # extract deltas
        trans = self.delta.trans[indicesTrans, :, :]
        absRx = self.delta.absRx[indicesAbsRx, :]
        absTx = self.delta.absTx[indicesAbsTx, :]

        if retune:
            # offset deltas
            if self.cfg.adnsEnable:
                trans = trans + self.offset
                absRx = absRx - self.offset
                absTx = absTx - self.offset

            # tune using offset deltas
            params = self.calcParams(trans, absRx, absTx, maxOrder, self.verbose == 1)

            # un-offset deltas
            if self.cfg.adnsEnable:
                trans = trans - self.offset
                absRx = absRx + self.offset
                absTx = absTx + self.offset
        else:
        # extract params
            params = copy.deepcopy(self.params)
            # extract basis vectors to max order
            params.basisVectorsTransRx = (params.TransBasis[:, :maxOrder] * 2**15).round().astype(np.int16)
            params.basisVectorsAbsRx = (params.AbsRxBasis[:, :maxOrder] * 2**15).round().astype(np.int16)
            params.basisVectorsAbsTx = (params.AbsTxBasis[:, :maxOrder] * 2**15).round().astype(np.int16)
        # trans fit and residual
        if trans.any():
            bvs = params.basisVectorsTransRx.astype(float) / 2 ** 15
            peakResTrans = np.zeros(maxOrder)
            nf = np.shape(trans)[0]
            for i in ind:
                for j in range(nf):
                    d = trans[j, :, :]
                    w = bvs[:, :i].T @ d.T
                    residual = d - (bvs[:, :i] @ w).T
                    peakResTrans[i-1] = max(peakResTrans[i-1], np.max(np.abs(residual.flatten())))

        # absRx fit and residual
        if absRx.any():
            bvs = params.basisVectorsAbsRx.astype(float) / 2 ** 15
            peakResAbsRx = np.zeros(maxOrder)
            for i in ind:
                w = bvs[:, :i].T @ absRx.T
                residual = absRx - (bvs[:, :i] @ w).T
                peakResAbsRx[i-1] = np.max(np.abs(residual.flatten()))

        # absTx fit and residual
        bvs = params.basisVectorsAbsTx.astype(float) / 2 ** 15
        peakResAbsTx = np.zeros(maxOrder)
        for i in ind:
            w = bvs[:, :i].T @ absTx.T
            residual = absTx - (bvs[:, :i] @ w).T
            peakResAbsTx[i-1] = np.max(np.abs(residual.flatten()))

        # print results
        if priorVerbose:
            print('\n   Peak Residue Magnitude vs. Order\n  \n')
            print('   Order ')
            for i in map(lambda x: x + 1, ind):
                print('{:8d}'.format(i))
            print('\r')
            # trans
            print('   Trans ')
            for i in ind:
                print('{:8.2f}'.format(peakResTrans[i]))
            print('\r')
            # absRx
            print('   AbsRx ')
            for i in ind:
                print('{:8.2f}'.format(peakResAbsRx[i]))
            print('\r')
            # absTx
            print('   AbsTx ')
            for i in ind:
                print('{:8.2f}'.format(peakResAbsTx[i]))
            print('\n')

        # restore verbose mode
        self.verbose = priorVerbose
        return peakResTrans, peakResAbsRx, peakResAbsTx
    # end evalOrder()_______________________________________

    def setMaskParams(self):
        peakResTrans, peakResAbsRx, peakResAbsTx = self.evalOrder()
        temp = np.nonzero(peakResTrans < 0.25*self.cfg.cSat)[0]
        order_t1 = min(self.order, temp[0]+1) if temp.size != 0 else self.order  # +1 since MATLAB is 1-based
        if self.verbose:
            print("First trans iteration order = {}".format(order_t1))

        stdTrans = np.zeros(self.order)
        stdAbsRx = np.zeros(self.order)
        stdAbsTx = np.zeros(self.order)
        for i in range(self.order):
            v = self.params.TransBasis
            sv = self.params.TransStd**2
            stdTrans[i] = max(np.sqrt(np.diag(v[:, i+1:] @ np.diag(sv[i+1:]) @ v[:, i+1:].T)))
            v = self.params.AbsRxBasis
            sv = self.params.AbsRxStd**2
            stdAbsRx[i] = max(np.sqrt(np.diag(v[:, i+1:] @ np.diag(sv[i+1:]) @ v[:, i+1:].T)))
            v = self.params.AbsTxBasis
            sv = self.params.AbsTxStd**2
            stdAbsTx[i] = max(np.sqrt(np.diag(v[:, i+1:] @ np.diag(sv[i+1:]) @ v[:, i+1:].T)))
        # trans order check #FIXME: ugly -1 due to 1-based indexing in MATLAB
        std_orders = np.minimum(max(order_t1, self.order - 2) + np.array([0, 1, 2]), self.order)
        res_orders = std_orders[[0, 0, 1]]
        trans_factors = peakResTrans[[res_orders-1]] / stdTrans[[std_orders-1]]  # -1 since Matlab is 1-based
        absrx_factors = peakResAbsRx[[self.order-1, min(4, self.order)-1]] / stdAbsRx[[min(4, self.order)-1, self.order-1]]
        abstx_factors = peakResAbsTx[[self.order-1, min(4, self.order)-1]] / stdAbsTx[[min(4, self.order)-1, self.order-1]]
        abstx_mfm_factors = peakResAbsTx[[0, 0, 1]] / stdAbsTx[[0, 1, self.order-1]]

        # set cgf params
        self.params.transOrderIter1 = order_t1
        self.params.transResThFactor1 = np.ceil(trans_factors[0]).astype(int)
        self.params.transResThFactor2 = np.ceil(trans_factors[1]).astype(int)
        self.params.transResThFactor3 = round(trans_factors[2])  # FIXME:*.5 exactly will result in one-off from MATLAB code, since MATLAB breaks ties away form zero
        self.params.absRxResThFactor1 = np.ceil(absrx_factors[0]).astype(int)
        self.params.absRxResThFactor2 = round(absrx_factors[1])
        self.params.absTxResThFactor1 = np.ceil(abstx_factors[0]).astype(int)
        self.params.absTxResThFactor2 = round(abstx_factors[1])
        self.params.absTxMfmResThFactor1 = np.ceil(abstx_mfm_factors[0]).astype(int)
        self.params.absTxMfmResThFactor2 = np.ceil(abstx_mfm_factors[1]).astype(int)
        self.params.absTxMfmResThFactor3 = round(abstx_mfm_factors[2])
        self.params.stdTrans = stdTrans
        self.params.stdAbsRx = stdAbsRx
        self.params.stdAbsTx = stdAbsTx


    def calcDelta(self, rawTrans, rawAbsRx, rawAbsTx, offset, verbose) -> Optional[Tuple[Union[list, Any], Union[list, Any], Union[list, Any]]]:
        # Parameters
        blFiltLen = 101

        # initialize outputs
        deltaTrans = []
        deltaAbsRx = []
        deltaAbsTx = []

        # trans
        if rawTrans.any():
            if verbose:
                print('\n Calculating trans delta...')
            trans_bl = self.calcBaseline(rawTrans, blFiltLen)  # use the original Matlab code's way of finding baseline
            deltaTrans = trans_bl + offset - rawTrans

        # check for abs data clipping
        global CLIP_CHECK_EN
        if CLIP_CHECK_EN:
            if np.any(rawAbsRx == 0) or np.any(rawAbsRx == 65520):
                cont = input('Abs RX training data clipped, do you want to continue? [y/n]:')
                if not (cont == '' or cont == 'y' or cont == 'Y'):  # enter or y pressed
                    return
                else:
                    usrinput = input('Skip further checks? [y/n]')
                    if usrinput == '' or usrinput == 'y' or usrinput == 'Y':
                        CLIP_CHECK_EN = False

            if np.any(rawAbsTx == 0) or np.any(rawAbsTx == 65520):
                cont = input('Abs TX training data clipped, do you want to continue? [y/n]:')
                if not (cont == '' or cont == 'y' or cont == 'Y'):
                    return
                else:
                    usrinput = input('Skip further checks? [y/n]')
                    if usrinput == '' or usrinput == 'y' or usrinput == 'Y':
                        CLIP_CHECK_EN = False

        # abs rx and abs tx
        if verbose:
            print('\nCalculating absRx and absTx delta...')
        if rawAbsRx.any():
            profx_bl = self.calcBaseline(rawAbsRx, blFiltLen)
            deltaAbsRx = rawAbsRx - profx_bl - offset
        if rawAbsTx.any():
            profy_bl = self.calcBaseline(rawAbsTx, blFiltLen)
            deltaAbsTx = rawAbsTx - profy_bl - offset

        return deltaTrans, deltaAbsRx, deltaAbsTx

    # end calcDelta()____________________________________________________________________________

    # __________________ STATIC METHODS ________________________________________________________

    @staticmethod
    def tuneData(files=None, verbose=1, outlier=0, augment=1):
        """
        Process collections in data file(s)
        Inputs:
            files = array of data filenames
            verbose = verbosity level (0=none, 1=text)
            outlier = enable to remove outliers from individual collections
            augment = enable data augmentation
        Outputs:
            params = PDNR configuration parameters for combined tuning
            results = cell array table of noise scores
        Example usage:
            params, results = pdnr_tool.selectData(files)
        """

        if not files:
            return
        if type(files) is not list:
            files = [files]
        # initialize
        results = []
        params = []
        pt = []
        num_files = len(files)  # number of input files

        # load data files
        pts = []  # list for individual pdnr_tools
        num_collections = np.inf  # number of collections (gears)
        for i in range(num_files):
            # instantiate
            p = pdnr_tool()
            p.verbose = 0
            # load data file
            status = p.loadData(files[i])
            if not status:
                print('\n  Exiting.  File {} not found.'.format(files[i]))
                return
            # set individual pdnr_tool
            pts.append(p)
            # update number of collections
            if p.collection.nc < num_collections:
                num_collections = p.collection.nc

        steps = 1
        for i in range(num_files):
            for j in range(num_collections):
                if outlier:
                    steps += 3
                if augment:
                    steps += 1
                elif not outlier:
                    steps += 2
        if num_files > 1 and num_collections > 1:
            for j in range(num_collections):
                if augment:
                    steps += 1
                else:
                    steps += 2
        if augment:
            steps += 1
        else:
            steps += 2
        steps += 1

        pdnr_tool.step = 0
        pdnr_tool.steps = steps
        print('total steps = {}'.format(steps))

        pdnr_tool.updateProgress()

        # process individual collections
        metrics_ij = [[0] * num_collections for i in range(num_files)]  # nested lists for individual collection metrics
        for i in range(num_files):
            # process collections
            if verbose:
                print(' Processing {}...'.format(pts[i].file.filename))
            for j in range(num_collections):
                # process collections
                if verbose and p.collection.nc > 1:
                    print(' Processing collection {}...'.format(j))
                pts[i].initMode(j)
                # if outlier checking is enabled find and remove them
                if outlier:
                    pts[i].tune()
                    pdnr_tool.updateProgress()
                    pts[i].fit()
                    pdnr_tool.updateProgress()
                    pts[i].removeOutliers(1)
                    pdnr_tool.updateProgress()
                # tune/fit/augment
                if augment:
                    pts[i].augment()
                    pdnr_tool.updateProgress()
                elif not outlier:
                    pts[i].tune()
                    pdnr_tool.updateProgress()
                    pts[i].fit()
                    pdnr_tool.updateProgress()
                # save individual collection results
                metrics_ij[i][j] = copy.deepcopy(pts[i].metrics)  # rows correspond to files, cols to collections

        # combined datasets for individual collections
        metrics_i = []  # list for combined individual collection metrics
        if num_files > 1 and num_collections > 1:
            if verbose:
                print(' Processing combined data...')
            for j in range(num_collections):
                # process collection
                if verbose:
                    print(' Processing collection {}...'.format(j))
                # initialize collection mode
                for i in range(num_files):
                    pts[i].initMode(j)  # mode is zero based
                # instantiate
                p = pdnr_tool()
                p.verbose = 0
                p.enables.outlier = 0
                # tune/fit/augment
                if augment:
                    p.augment(3, 200, pts)
                    pdnr_tool.updateProgress()
                else:
                    p.tuneDeltas(pts)
                    pdnr_tool.updateProgress()
                    p.fit()
                    pdnr_tool.updateProgress()
                # save combined collection results
                metrics_i.append(copy.deepcopy(p.metrics))

        # combined all datasets and collections
        if verbose:
            print(' Processing combined data and collections...')
        # instantiate
        pt = pdnr_tool()
        pt.verbose = 0
        pt.enables.outlier = 0  # disable outlier check in combined fits
        # initialize to all collections
        for j in range(num_files):
            pts[j].initMode(-1)
        # augmented combined fit
        if augment:
            pt.augment(3, 200, pts)
            pdnr_tool.updateProgress()
        else:
            pt.tuneDeltas(pts)
            pdnr_tool.updateProgress()
            pt.fit()
            pdnr_tool.updateProgress()
        # set mask parameters
        pt.setMaskParams()
        pdnr_tool.updateProgress()
        # set parameters
        params = copy.deepcopy(pt.params)

        # set results _______________________________
        header = ['Data', 'Coll', 'Trans', 'AbsRx', 'AbsTx']
        results = np.array(header)
        subframes = ['trans', 'absRx', 'absTx']
        lsf = len(subframes)
        # individual collection results
        for i in range(num_files):
            for j in range(num_collections):
                ds = 'D{}'.format(i + 1)
                cs = 'C{}'.format(j)
                ns = [0 for _ in range(lsf)]
                for k in range(lsf):
                    if not getattr(metrics_ij[i][j], subframes[k]):
                        ns[k] = 'N/A'
                    else:
                        ns[k] = getattr(metrics_ij[i][j], subframes[k]).peakRes
                results = np.vstack((results, np.array([ds, cs, ns[0], ns[1], ns[2]], dtype='O')))

        # combined collection results
        for i in range(len(metrics_i)):
            cs = 'C{}'.format(i)
            ns = [0 for _ in range(lsf)]
            for k in range(lsf):
                if not getattr(metrics_i[i], subframes[k]):
                    ns[k] = 'N/A'
                else:
                    ns[k] = getattr(metrics_i[i], subframes[k]).peakRes
            results = np.vstack((results, np.array(['All', cs, ns[0], ns[1], ns[2]], dtype='O')))

        # combined data and collection results
        ns = [0 for _ in range(lsf)]
        for k in range(lsf):
            if not getattr(pt.metrics, subframes[k]):
                ns[k] = 'N/A'
            else:
                ns[k] = getattr(pt.metrics, subframes[k]).peakRes
        results = np.vstack((results, np.array(['All', 'All', ns[0], ns[1], ns[2]], dtype='O')))

        # print results
        if verbose:
            print('\nCollection Results:')
            print('{:8s}{:8s}{:^10s} {:8s}{:8s}'.format(*results[0]))
            for i in range(1, np.shape(results)[0]):
                print('{:8s}{:8s}{:8.2f}{:8.2f}{:8.2f}'.format(*results[i]))

        pdnr_tool.params = params
        pdnr_tool.results = results
        return params, results

    # end tuneData()__________________________________________________________

    @staticmethod
    def selectData(files, subframes=None, stride=1, verbose=1):
        """
        Select input data to optimize tuning
        Inputs:
            files = cell array of data file names
            subframes = array (sub)set of ['trans', 'absRx', 'absTx']
            stride = subsample rate
            verbose = verbosity level (0=none, 1=text)
        Outputs:
            params = PDNR configuration parameters corresponding to data selection
            results = structure of cell arrays of data selections and initial and final metrics
        Usage example
            subframes = ['absRx']
            stride = 1
            verbose = 1
            params, results = pdnr_tool.selectData(files, subframes, stride, verbose)
        """

        # defaults and initializations
        if subframes is None:  # to avoid mutable default function argument
            subframes = ['trans', 'absRx', 'absTx']
        params = []
        results = Results()
        num_files = len(files)

        # measure time taken
        if verbose:
            tic = time.time()

        # load data files(s)
        pts = []  # cell array for individual pdnr_tools
        if num_files > 1:  # multiple input data files - selection is over data files
            # process individual files
            for i in range(num_files):
                p = pdnr_tool()
                p.verbose = 0
                p.stride = stride
                status = p.loadData(files[i])
                if not status:
                    print('\n   Exiting. Input file {} not found.'.format(files[i]))
                    return
                p.verbose = 1
                # set individual pdnr_tool
                pts.append(p)
                if verbose:
                    print(' Loaded {}...'.format(p.file.filename))
        else:  # only one input data file - selection is over collections
            # process individual collections
            max_collections = 1000
            for j in range(max_collections):
                p = pdnr_tool()
                p.verbose = 0
                p.stride = stride
                status = p.loadData(files[0])
                if not status:
                    print('\n   Exiting. Input file {} not found.'.format(files[0]))
                    return
                nc = p.collection.nc
                if nc <= 1:
                    print('\n   Exiting. Input file {} does not contain multiple collections'.format(files[0]))
                    return
                # process collection
                p.initMode(j)  # mode is zero-based
                p.verbose = 1
                # set individual pdnr_tool
                pts.append(p)
                if verbose:
                    print(' Loaded collection {}...'.format(j))
                if j == nc-1:
                    break

        steps = 1
        if 'trans' in subframes:
            steps += 1
        if 'absRx' in subframes:
            steps += 1
        if 'absTx' in subframes:
            steps += 1
        for sf in range(len(subframes)):
            subframe = subframes[sf]
            steps += 1
            if subframe == 'trans':
                steps += 1
            if subframe == 'absRx':
                steps += 1
            if subframe == 'absTx':
                steps += 1
            if subframe == 'trans':
                steps += 1
            if subframe == 'absRx':
                steps += 1
            if subframe == 'absTx':
                steps += 1
            steps += 1

        pdnr_tool.step = 0
        pdnr_tool.steps = steps
        print('total steps = {}'.format(steps))

        pdnr_tool.updateProgress()

        # nominal performance
        if verbose:
            print(' Calculating nominal performance...')
        # instantiate
        p0 = pdnr_tool()
        p0.verbose = 0
        p0.enables.outlier = 0  # disable outlier check in combined fits
        # augment
        if 'trans' in subframes:
            p0.augmentTrans(3, 200, pts)
            pdnr_tool.updateProgress()
        if 'absRx' in subframes:
            p0.augmentAbsRx(3, 200, pts)
            pdnr_tool.updateProgress()
        if 'absTx' in subframes:
            p0.augmentAbsTx(3, 200, pts)
            pdnr_tool.updateProgress()

        # initialize
        data_labels = np.array([])
        npts = len(pts)
        for i in range(npts):
            if num_files > 1:
                data_labels = np.append(data_labels, pts[i].file.filename)
            else:
                data_labels = np.append(data_labels, ['Collection ' + str(i+1)])

        ind0 = np.arange(npts)
        nsf = len(subframes)
        results.selection = np.zeros((2, nsf), dtype=object)
        results.metric = np.zeros((2, nsf), dtype=object)
        total_iter = int(nsf * (npts - 1) * (1 + len(ind0) / 2))
        current_iter = 0
        params = p0.params

        # eliminate non performers using individual deltas
        for sf in range(nsf):
            ind = copy.deepcopy(ind0)
            subframe = subframes[sf]  # subframe name
            # calculate effect of individual dataset
            if verbose:
                print('\n Initiating {}...'.format(subframe))
            results.selection[0, sf] = subframe  # first row is subframe name
            results.metric[0, sf] = subframe
            for iter in range(npts - 1):
                metrics = []
                if verbose:
                    print(' Initiating iteration {}'.format(iter))
                for i in range(len(ind)):
                    current_iter = current_iter + 1
                    p = pdnr_tool()
                    p.verbose = 0
                    p.enables.outlier = 0  # disable outlier check in combined fits

                    # remove dataset
                    idiff = np.setdiff1d(ind, ind[i])
                    # tune reduced dataset
                    pts_idiff = [pts[i] for i in idiff]
                    p.tuneDeltas(pts_idiff)
                    if subframe == 'trans':
                        p.augmentTrans(3, 200, pts_idiff)
                    if subframe == 'absRx':
                        p.augmentAbsRx(3, 200, pts_idiff)
                    if subframe == 'absTx':
                        p.augmentAbsTx(3, 200, pts_idiff)
                    params_select = p.params

                    # fit entire dataset
                    p = copy.deepcopy(p0)  # copy entire data, re-instantiating p
                    p.params = copy.deepcopy(params_select)  # replace with reduced dataset tuning
                    if subframe == 'trans':
                        p.fitTrans()
                    if subframe == 'absRx':
                        p.fitAbsRx()
                    if subframe == 'absTx':
                        p.fitAbsTx()

                    metrics.append(getattr(p.metrics, subframe).peakRes)
                    if verbose:
                        print(' Sub iteration {} complete.'.format(i))

                # calculate relative performance using all datasets to reduced dataset tuning
                # err(i) is delta peak residual error resulting from tuning w/o dataset i applied to entire dataset
                # positive error implies eliminated dataset i is rich/important
                # negative error implies tuning is better without eliminated dataset i
                err = np.array(metrics) - getattr(p0.metrics, subframe).peakRes

                # sort errors
                i_sort = np.argsort(err)[::-1]  # descending order
                err_sorted = [err[i] for i in i_sort]
                results.selection[1, sf] = data_labels[ind[i_sort]].T  # second row is selections
                if verbose:
                    print('    Cost    Data')
                    for i in range(len(err_sorted)):
                        print('{:8.2f}    {}'.format(err_sorted[i], results.selection[1, sf][i]))

                # update progress
                if verbose:
                    print(' Iterations {:.1f}% complete.'.format(100 * (current_iter) / total_iter))

                # exit if all selected datasets are important
                cutoff = np.sum(np.array(err_sorted) > 0)
                if cutoff == len(err_sorted):
                    break
                cutoff = np.sum(np.array(err_sorted) <= 0)
                if cutoff == len(err_sorted):
                    break

                # update results if last iteration
                if iter == npts - 2:
                    results.selection[1, sf] = data_labels[ind[i_sort[:-1]]].T  # second row is selections

                # remove least important dataset index from tuning
                ind = np.setdiff1d(ind, ind[i_sort[-1]])

            # instantiate
            p = pdnr_tool()
            p.verbose = 0
            p.enables.outlier = 0  # disable outlier check in combined fits
            # tune with selected data
            pts_ind = [pts[i] for i in ind]
            p.tuneDeltas(pts_ind)
            pdnr_tool.updateProgress()
            # augment
            if subframe == 'trans':
                p.augmentTrans(3, 200, pts_ind)
                pdnr_tool.updateProgress()
            if subframe == 'absRx':
                p.augmentAbsRx(3, 200, pts_ind)
                pdnr_tool.updateProgress()
            if subframe == 'absTx':
                p.augmentAbsTx(3, 200, pts_ind)
                pdnr_tool.updateProgress()
            params_select = copy.deepcopy(p.params)

            # fit entire data with selected data tuning parameters
            p = copy.deepcopy(p0)  # copy entire data, re-instantiating p
            p.params = copy.deepcopy(params_select)  # replace parameters with selected data parameters
            if subframe == 'trans':
                p.fitTrans()
                pdnr_tool.updateProgress()
            if subframe == 'absRx':
                p.fitAbsRx()
                pdnr_tool.updateProgress()
            if subframe == 'absTx':
                p.fitAbsTx()
                pdnr_tool.updateProgress()
            p.setMaskParams()
            pdnr_tool.updateProgress()
            results.metric[1, sf] = np.array(
                [getattr(p0.metrics, subframe).peakRes, getattr(p.metrics, subframe).peakRes])  # second row is initial and final ns

            # save selected data parameters
            if subframe == 'trans':
                params.basisAmpStdevTransRx = p.params.basisAmpStdevTransRx
                params.basisVectorsTransRx = p.params.basisVectorsTransRx
                params.TransStd = p.params.TransStd
                params.TransBasis = p.params.TransBasis
                params.residualCovarianceTransRx = p.params.residualCovarianceTransRx
                params.stdTrans = p.params.stdTrans
                params.transResThFactor1 = p.params.transResThFactor1
                params.transResThFactor2 = p.params.transResThFactor2
                params.transResThFactor3 = p.params.transResThFactor3
                params.transOrderIter1 = p.params.transOrderIter1
            if subframe == 'absRx':
                params.basisAmpStdevAbsRx = p.params.basisAmpStdevAbsRx
                params.basisVectorsAbsRx = p.params.basisVectorsAbsRx
                params.AbsRxStd = p.params.AbsRxStd
                params.AbsRxBasis = p.params.AbsRxBasis
                params.residualCovarianceAbsRx = p.params.residualCovarianceAbsRx
                params.stdAbsRx = p.params.stdAbsRx
                params.absRxResThFactor1 = p.params.absRxResThFactor1
                params.absRxResThFactor2 = p.params.absRxResThFactor2
            if subframe == 'absTx':
                params.basisAmpStdevAbsTx = p.params.basisAmpStdevAbsTx
                params.basisVectorsAbsTx = p.params.basisVectorsAbsTx
                params.AbsTxStd = p.params.AbsTxStd
                params.AbsTxBasis = p.params.AbsTxBasis
                params.residualCovarianceAbsTx = p.params.residualCovarianceAbsTx
                params.stdAbsTx = p.params.stdAbsTx
                params.absTxResThFactor1 = p.params.absTxResThFactor1
                params.absTxResThFactor2 = p.params.absTxResThFactor2
                params.absTxMfmResThFactor1 = p.params.absTxMfmResThFactor1
                params.absTxMfmResThFactor2 = p.params.absTxMfmResThFactor2
                params.absTxMfmResThFactor3 = p.params.absTxMfmResThFactor3

            if verbose:
                print(' Completed {}.'.format(subframe))

        # display results
        if verbose:
            # calculate selection table sizes (used in printing selection results below)
            mh = 0  # max height, maximum number of selected input files for all subframe types
            mw = 0  # max width, maximum input file name length from all selections
            for sf in range(nsf):
                h = len(results.selection[1, sf])  # second row is selections
                if h > mh:
                    mh = h
                for j in range(h):
                    w = len(results.selection[1, sf][j])  # second row is selections
                    if w > mw:
                        mw = w

            mw = mw + 2  # add 2 spaces buffer between table entries

            # print selections
            print('Selection Data:')
            # subframe types
            for sf in range(nsf):
                print('{:>{WIDTH}}'.format(subframes[sf], WIDTH=mw), end='')
            print('\n')
            # subframe selections
            for i in range(mh):
                for sf in range(nsf):
                    if i < len(results.selection[1, sf]):  # second row is selections
                        print('{:>{WIDTH}}'.format(results.selection[1, sf][i], WIDTH=mw), end='')
                    else:
                        print('{:>{WIDTH}}'.format('', WIDTH=mw), end='')
                print('\n')

            # print results (noise scores)
            print('Selection Results:')
            # subframe types
            print('        ', end='')
            for sf in range(nsf):
                print('{:>8}'.format(subframes[sf]), end='')
            # print('\n')
            # original scores from all data
            print('\ninitial:', end='')
            for sf in range(nsf):
                print('{:>8.2f}'.format(results.metric[1, sf][0]), end='')  # top second row is initial ns
            # final scores from selected data
            print('\n  final:', end='')
            for sf in range(nsf):
                print('{:>8.2f}'.format(results.metric[1, sf][1]), end='')  # bottom second row is final ns
            print('\n')

            # stop test timer
            toc = time.time() - tic
            print('Time elapsed: {:.2f} seconds'.format(toc))

        pdnr_tool.params = params
        pdnr_tool.results = results
        return params, results

    # end selectData()______________________________________________________________________________

    @staticmethod
    def updateProgress():
        pdnr_tool.step += 1
        print('step {}'.format(pdnr_tool.step))
        print(json.dumps({"state": "running", "progress": math.floor(pdnr_tool.step / pdnr_tool.steps * 100)}))

    @staticmethod
    def getResults():
        return {"params": pdnr_tool.params, "results": pdnr_tool.results}

    @staticmethod
    def calcBaseline(rawFrames: np.array, blFiltLen: int) -> np.array:
        """
        Calculates baseline for raw frames in rawFrames array (frames
        dimension must be the first one).
        Input:
            rawFrames = frame data
            blFiltLen = filter length
        Output:
            baseline = estimated baseline data
        """
        numFrames = np.shape(rawFrames)[0]

        # Limit the moving average filter length by the number of available
        # frames (needed to handle short data).
        blFiltLen = min(blFiltLen, numFrames)

        # Calculate baseline using moving average (use mean on the edges).
        baseline = lfilter(np.ones(blFiltLen), blFiltLen, rawFrames, axis=0)
        headLen = np.ceil((blFiltLen - 1) / 2).astype(int)
        tailLen = np.floor((blFiltLen - 1) / 2).astype(int)
        if rawFrames.ndim > 2:
            headdims = (headLen, 1, 1)
            taildims = (tailLen, 1, 1)
        else:
            headdims = (headLen, 1)
            taildims = (tailLen, 1)

        baseline = np.concatenate((np.tile(np.mean(rawFrames[0:blFiltLen, ...], axis=0), headdims),
                                   baseline[blFiltLen - 1:, ...],
                                   np.tile(np.mean(rawFrames[numFrames - blFiltLen:, ...], axis=0),
                                           taildims))
                                  )

        return baseline


# end calcBaseline()____________________________________________________________________


# _____________________________________________ DEBUG FUNCTIONS ________________________________________________________

def run_tests(path_to_dataset, **kwargs):
    """
    Run through both tuneData() and selectData() printing their corresponding outputs in the console window
    Only intended for quick testing.
    Inputs: path_to_dataset: path to the test directory containing the xml file(s)
            numfiles: Number of files in the test dataset to use. -1 (default) to use all
            verbose: Enable verbose output
            outlier: Enable outlier removal
            augment: Enable augmentation
            stride: Stride size
            subframes: Subframes to use in selectData()
    Output: Tuning stats printed in console window and stored in corresponding function's output data structures
    """
    # select xml files in the chosen dataset directory
    files_list = [os.path.join(path_to_dataset, i) for i in os.listdir(path_to_dataset) if i.endswith('.xml')]
    files = files_list if kwargs['numfiles'] == -1 else files_list[:kwargs['numfiles']]
    # do accutune!
    print("Running tuneData() with parameters: verbose={}, outlier={}, augment={}".format(kwargs['verbose'],kwargs['outlier'],kwargs['augment']))
    params_t, results_t = pdnr_tool.tuneData(files, verbose=kwargs['verbose'], outlier=kwargs['outlier'], augment=kwargs['augment'])
    if 'params_t' in locals():
        print('absRxResThFactor1 ', params_t.absRxResThFactor1, 'absRxResThFactor2 ', params_t.absRxResThFactor2)
        print('absTxResThFactor1 ', params_t.absTxResThFactor1, 'absTxResThFactor2 ', params_t.absTxResThFactor2)
        print('transResThFactor1 ', params_t.transResThFactor1, 'transResThFactor2 ', params_t.transResThFactor2, 'transResThFactor3 ', params_t.transResThFactor3)
        print('absTxMfmResThFactor1 ', params_t.absTxMfmResThFactor1, 'absTxMfmResThFactor2 ', params_t.absTxMfmResThFactor2, 'absTxMfmResThFactor3 ', params_t.absTxMfmResThFactor3)

    print("Running selectData() with parameters: verbose:={}, subframes={}, stride={}".format(kwargs['verbose'], kwargs['subframes'], kwargs['stride']))
    params_s, results_s = pdnr_tool.selectData(files, subframes=kwargs['subframes'], stride=kwargs['stride'], verbose=kwargs['verbose'])
    if 'params_s' in locals():
        print('absRxResThFactor1 ', params_s.absRxResThFactor1, 'absRxResThFactor2 ', params_s.absRxResThFactor2)
        print('absTxResThFactor1 ', params_s.absTxResThFactor1, 'absTxResThFactor2 ', params_s.absTxResThFactor2)
        print('transResThFactor1 ', params_s.transResThFactor1, 'transResThFactor2 ', params_s.transResThFactor2, 'transResThFactor3 ', params_s.transResThFactor3)
        print('absTxMfmResThFactor1 ', params_s.absTxMfmResThFactor1, 'absTxMfmResThFactor2 ', params_s.absTxMfmResThFactor2, 'absTxMfmResThFactor3 ', params_s.absTxMfmResThFactor3)

    return params_t, results_t, params_s, results_s


# _______________________________________________________________________________________________________________________

if __name__ == '__main__':
    import platform
    import subprocess
    from argparse import ArgumentParser, RawTextHelpFormatter

    p = ArgumentParser(description=__doc__, formatter_class=RawTextHelpFormatter)
    p.add_argument('--tests_dirname', '-d', help='Name of the directory containing all test data directories. Can be in cwd or up the git tree', default='tests')
    p.add_argument('--test_name', '-t', help='Name of the specific test dataset (directory) to use', default='GS21_PR3566694')
    p.add_argument('--numfiles', '-n', help='Number of files in the test dataset to use. -1 (default) to use all', type=int, default=-1)
    p.add_argument('--verbose', '-v', help='Output verbosity', type=int, default=1)
    p.add_argument('--outlier', '-o', help='Enable outlier removal for tuneData()', type=int, default=0)
    p.add_argument('--augment', '-a', help='Enable data augmentation for tuneData()', type=int, default=1)
    p.add_argument('--subframes', '-s', nargs='+', help='Subframe types to use in selectData()', choices=['trans', 'absRx', 'absTx'], default=['trans', 'absRx', 'absTx'])
    p.add_argument('--stride', '-r', help='Select stride size for selectData()', type=int, default=1)

    args = p.parse_args()

    print("Python platform architecture: ", platform.architecture()[0]) # for debugging
    tests_dirname = args.tests_dirname
    try:
        path_to_tests = os.path.join(os.getcwd(), tests_dirname)  # allow tests directory to be found in cwd
        if not os.path.isdir(path_to_tests):
            git_root = subprocess.Popen(['git', 'rev-parse', '--show-toplevel'], stdout=subprocess.PIPE).communicate()[0].rstrip().decode('utf-8')
            path_to_tests = os.path.join(git_root, tests_dirname)
        assert os.path.isdir(path_to_tests)
    except Exception as e:
        if type(e) == AssertionError:
            print("Error: Could not find tests directory. Exiting.")
        else:
            raise

    print('Running using test data in \"{}\" directory'.format(args.test_name))
    testToRun = os.path.join(path_to_tests, args.test_name)
    params_t, results_t, params_s, results_s = run_tests(testToRun,
                                                         numfiles=args.numfiles,
                                                         verbose=args.verbose,
                                                         outlier=args.outlier,
                                                         augment=args.augment,
                                                         subframes=args.subframes,
                                                         stride=args.stride)

    print('Done!')
