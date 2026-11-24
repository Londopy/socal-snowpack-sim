"""Peaks analysed, grouped by touring area.

Coordinates are approximate. terrain.py snaps each one to the highest DEM cell
within 150 m and compares that elevation with the listed one, so a wrong
coordinate shows up as a mismatch instead of silently analysing the wrong hill.
"""

PEAKS = [
    # slug, name, area, lat, lon, listed elevation (ft)
    ("baldy", "Mt. Baldy (San Antonio)", "Baldy area", 34.2889, -117.6464, 10064),
    ("harwood", "Mt. Harwood", "Baldy area", 34.2871, -117.6343, 9552),
    ("dawson", "Dawson Peak", "Baldy area", 34.3032, -117.6364, 9575),
    ("pine", "Pine Mountain", "Baldy area", 34.3137, -117.6443, 9648),
    ("thunder", "Thunder Mountain", "Baldy area", 34.2651, -117.6058, 8587),
    ("telegraph", "Telegraph Peak", "Baldy area", 34.2617, -117.5981, 8985),
    ("timber", "Timber Mountain", "Baldy area", 34.2451, -117.5938, 8303),
    ("cucamonga", "Cucamonga Peak", "Cucamonga / Icehouse", 34.2228, -117.5853, 8859),
    ("bighorn_peak", "Bighorn Peak", "Cucamonga / Icehouse", 34.2337, -117.5976, 8441),
    ("ontario", "Ontario Peak", "Cucamonga / Icehouse", 34.2278, -117.6239, 8693),
    ("wright", "Wright Mountain", "Wrightwood / Blue Ridge", 34.3336, -117.6328, 8505),
    ("baden_powell", "Mt. Baden-Powell", "Angeles Crest", 34.3586, -117.7647, 9399),
    ("burnham", "Mt. Burnham", "Angeles Crest", 34.3591, -117.7814, 8997),
    ("throop", "Throop Peak", "Angeles Crest", 34.3497, -117.7989, 9138),
    ("hawkins", "Mt. Hawkins", "Angeles Crest", 34.3412, -117.8056, 8850),
    ("lewis", "Mt. Lewis", "Angeles Crest", 34.3727, -117.8061, 8396),
    ("islip", "Mt. Islip", "Angeles Crest", 34.3439, -117.8392, 8250),
    ("williamson", "Mt. Williamson", "Angeles Crest", 34.3711, -117.8581, 8214),
    ("waterman", "Waterman Mountain", "Angeles Crest", 34.3364, -117.9358, 8038),
    ("san_gorgonio", "San Gorgonio Mountain", "San Gorgonio Wilderness", 34.0992, -116.8250, 11503),
    ("jepson", "Jepson Peak", "San Gorgonio Wilderness", 34.1028, -116.8447, 11205),
    ("bighorn_mtn", "Bighorn Mountain", "San Gorgonio Wilderness", 34.0906, -116.8187, 10997),
    ("dragons_head", "Dragon's Head", "San Gorgonio Wilderness", 34.0898, -116.8307, 10866),
    ("dobbs", "Dobbs Peak", "San Gorgonio Wilderness", 34.0981, -116.8597, 10459),
    ("charlton", "Charlton Peak", "San Gorgonio Wilderness", 34.1145, -116.8536, 10806),
    ("shields", "Shields Peak", "San Gorgonio Wilderness", 34.1270, -116.8817, 10680),
    ("anderson", "Anderson Peak", "San Gorgonio Wilderness", 34.1245, -116.8945, 10840),
    ("sb_east", "San Bernardino East Peak", "San Gorgonio Wilderness", 34.1257, -116.9104, 10691),
    ("sb_peak", "San Bernardino Peak", "San Gorgonio Wilderness", 34.1222, -116.9233, 10649),
    ("grinnell", "Grinnell Mountain", "San Gorgonio Wilderness", 34.1261, -116.8089, 10284),
    ("sugarloaf", "Sugarloaf Mountain", "Big Bear", 34.1987, -116.8141, 9952),
    ("san_jacinto", "San Jacinto Peak", "San Jacinto", 33.8147, -116.6794, 10834),
    ("jean", "Jean Peak", "San Jacinto", 33.8062, -116.6790, 10670),
    ("marion", "Marion Mountain", "San Jacinto", 33.7959, -116.6867, 10362),
]
