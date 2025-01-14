# Copyright (C) 2011 Lukas Lalinsky
# (Minor modifications by Adrian Sampson.)
# Distributed under the MIT license, see the LICENSE file for details.

"""Low-level ctypes wrapper from the chromaprint library."""

import sys
import ctypes

if sys.version_info[0] >= 3:
    BUFFER_TYPES = (memoryview, bytearray,)
    BYTES_TYPE = bytes
elif sys.version_info[1] >= 7:
    BUFFER_TYPES = (buffer, memoryview, bytearray,)  # noqa: F821
    BYTES_TYPE = str
else:
    BUFFER_TYPES = (buffer, bytearray,)  # noqa: F821
    BYTES_TYPE = str


# Find the base library and declare prototypes.

def _guess_lib_name():
    if sys.platform == 'darwin':
        return ('libchromaprint.1.dylib', 'libchromaprint.0.dylib')
    elif sys.platform == 'win32':
        return ('chromaprint.dll', 'libchromaprint.dll')
    elif sys.platform == 'cygwin':
        return ('libchromaprint.dll.a', 'cygchromaprint-1.dll',
                'cygchromaprint-0.dll')
    return ('libchromaprint.so.1', 'libchromaprint.so.0')


for name in _guess_lib_name():
    try:
        _libchromaprint = ctypes.cdll.LoadLibrary(name)
        break
    except OSError:
        pass
else:
    raise ImportError("couldn't find libchromaprint")


_libchromaprint.chromaprint_get_version.argtypes = ()
_libchromaprint.chromaprint_get_version.restype = ctypes.c_char_p

_libchromaprint.chromaprint_new.argtypes = (ctypes.c_int,)
_libchromaprint.chromaprint_new.restype = ctypes.c_void_p

_libchromaprint.chromaprint_free.argtypes = (ctypes.c_void_p,)
_libchromaprint.chromaprint_free.restype = None

_libchromaprint.chromaprint_start.argtypes = \
    (ctypes.c_void_p, ctypes.c_int, ctypes.c_int)
_libchromaprint.chromaprint_start.restype = ctypes.c_int

_libchromaprint.chromaprint_feed.argtypes = \
    (ctypes.c_void_p, ctypes.POINTER(ctypes.c_char), ctypes.c_int)
_libchromaprint.chromaprint_feed.restype = ctypes.c_int

_libchromaprint.chromaprint_finish.argtypes = (ctypes.c_void_p,)
_libchromaprint.chromaprint_finish.restype = ctypes.c_int

_libchromaprint.chromaprint_get_fingerprint.argtypes = \
    (ctypes.c_void_p, ctypes.POINTER(ctypes.c_char_p))
_libchromaprint.chromaprint_get_fingerprint.restype = ctypes.c_int

_libchromaprint.chromaprint_decode_fingerprint.argtypes = \
    (ctypes.POINTER(ctypes.c_char), ctypes.c_int,
     ctypes.POINTER(ctypes.POINTER(ctypes.c_int32)),
     ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int), ctypes.c_int)
_libchromaprint.chromaprint_decode_fingerprint.restype = ctypes.c_int

_libchromaprint.chromaprint_encode_fingerprint.argtypes = \
    (ctypes.POINTER(ctypes.c_int32), ctypes.c_int, ctypes.c_int,
     ctypes.POINTER(ctypes.POINTER(ctypes.c_char)),
     ctypes.POINTER(ctypes.c_int), ctypes.c_int)
_libchromaprint.chromaprint_encode_fingerprint.restype = ctypes.c_int

_libchromaprint.chromaprint_dealloc.argtypes = (ctypes.c_void_p,)
_libchromaprint.chromaprint_dealloc.restype = None


# Main interface.

class FingerprintError(Exception):
    """Raised when a call to the underlying library fails."""


def _check(res):
    """Check the result of a library call, raising an error if the call
    failed.
    """
    if res != 1:
        raise FingerprintError()


class Fingerprinter(object):

    ALGORITHM_TEST1 = 0
    ALGORITHM_TEST2 = 1
    ALGORITHM_TEST3 = 2
    ALGORITHM_DEFAULT = ALGORITHM_TEST2

    def __init__(self, algorithm=ALGORITHM_DEFAULT):
        self._ctx = _libchromaprint.chromaprint_new(algorithm)

    def __del__(self):
        _libchromaprint.chromaprint_free(self._ctx)
        del self._ctx

    def start(self, sample_rate, num_channels):
        """Initialize the fingerprinter with the given audio parameters.
        """
        _check(_libchromaprint.chromaprint_start(
            self._ctx, sample_rate, num_channels
        ))

    def feed(self, data):
        """Send raw PCM audio data to the fingerprinter. Data may be
        either a bytestring or a buffer object.
        """
        if isinstance(data, BUFFER_TYPES):
            data = BYTES_TYPE(data)
        elif not isinstance(data, bytes):
            raise TypeError('data must be bytes, buffer, or memoryview')
        _check(_libchromaprint.chromaprint_feed(
            self._ctx, data, len(data) // 2
        ))

    def finish(self):
        """Finish the fingerprint generation process and retrieve the
        resulting fignerprint as a bytestring.
        """
        _check(_libchromaprint.chromaprint_finish(self._ctx))
        fingerprint_ptr = ctypes.c_char_p()
        _check(_libchromaprint.chromaprint_get_fingerprint(
            self._ctx, ctypes.byref(fingerprint_ptr)
        ))
        fingerprint = fingerprint_ptr.value
        _libchromaprint.chromaprint_dealloc(fingerprint_ptr)
        return fingerprint


def decode_fingerprint(data, base64=True):
    result_ptr = ctypes.POINTER(ctypes.c_int32)()
    result_size = ctypes.c_int()
    algorithm = ctypes.c_int()
    _check(_libchromaprint.chromaprint_decode_fingerprint(
        data, len(data), ctypes.byref(result_ptr), ctypes.byref(result_size),
        ctypes.byref(algorithm), 1 if base64 else 0
    ))
    result = result_ptr[:result_size.value]
    _libchromaprint.chromaprint_dealloc(result_ptr)
    return result, algorithm.value


def encode_fingerprint(fingerprint, algorithm, base64=True):
    fp_array = (ctypes.c_int * len(fingerprint))()
    for i in range(len(fingerprint)):
        fp_array[i] = fingerprint[i]
    result_ptr = ctypes.POINTER(ctypes.c_char)()
    result_size = ctypes.c_int()
    _check(_libchromaprint.chromaprint_encode_fingerprint(
        fp_array, len(fingerprint), algorithm, ctypes.byref(result_ptr),
        ctypes.byref(result_size), 1 if base64 else 0
    ))
    result = result_ptr[:result_size.value]
    _libchromaprint.chromaprint_dealloc(result_ptr)
    return result
