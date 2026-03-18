"""Configuration for cross-asset skewness notebook workflow."""

LOOKBACK = 256
HISTORY_DAYS = 3650  # ~10 years
VOL_TARGET = 0.10

UNIVERSE = [
    (
        "Equity",
        [
            "SPY",
            "EWU",
            "EWJ",
            "INDA",
            "EWG",
            "EWL",
            "EWP",
            "EWQ",
            "VTI",
            "FXI",
            "EWZ",
            "EWY",
            "EWA",
            "EWC",
            "EWG",
            "EWH",
            "EWI",
            "EWN",
            "EWD",
            "EWT",
            "EZA",
            "EWW",
            "ENOR",
            "EDEN",
            "TUR",
        ],
    ),
    (
        "FI",
        [
            "AGG",
            "TLT",
            "LQD",
            "JNK",
            "MUB",
            "MBB",
            "IAGG",
            "IGOV",
            "EMB",
            "BND",
            "BNDX",
            "VCIT",
            "VCSH",
            "BSV",
            "SRLN",
        ],
    ),
    ("Commodities", ["GLD", "SLV", "GSG", "USO", "PPLT", "UNG", "DBA"]),
    ("Other", ["IYR", "REET", "USRT", "ICF", "VNQ"]),
    ("Ccy", ["UUP", "FXY", "FXE", "FXF", "FXB", "FXA", "FXC"]),
]

FACTOR_TICKERS = ["MTUM", "VTV", "VUG", "VIG"]
SAMPLE_TICKERS = ["SPY", "GLD", "AGG"]
SAMPLE_WEIGHT_TICKERS = ["SPY", "AGG", "GLD"]
