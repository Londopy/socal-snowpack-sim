"""The zone grid: 8 aspects x 5 elevation bands on a 38-degree slope."""
import numpy as np

LAT = 34.28
SLOPE = 38.0
ASPECTS = np.arange(0, 360, 45.0)                      # N, NE, E, SE, S, SW, W, NW
ASP_NAMES = ["N", "NE", "E", "SE", "S", "SW", "W", "NW"]
BAND_EDGES_M = np.array([2000.0, 2300.0, 2600.0, 2900.0, 3200.0, 3510.0])
BANDS_M = (BAND_EDGES_M[:-1] + BAND_EDGES_M[1:]) / 2.0  # band mid elevations
BAND_NAMES = ["%s-%s ft" % (format(int(round(a * 3.28084, -2)), ","), format(int(round(b * 3.28084, -2)), ","))
              for a, b in zip(BAND_EDGES_M[:-1], BAND_EDGES_M[1:])]
NB = len(BANDS_M)
MID = 2      # 8,500-9,500 ft band, used for the summary statistics
HIGH_B = 3   # 9,500-10,500 ft band
Z_REF = 2600.0
LAPSE = 0.0065
START_DOY = 319                                        # 15 Nov
NDAYS = 167                                            # to 30 Apr
PROBLEMS = ["storm", "wind", "wet", "persistent"]
