import json
from ocr.parse_slip import ocr_image_to_text
from ocr.document_classifier import classify_document
from ocr.parse_stock import parse_stock_confirmation_text

FILES = [
    "STKBML20260724062705163916.png",
    "STKBML20260724063024164733.png",
    "STKBML20260724063455166019.png",
    "STKBML20260724063642166556.png",
]

FIELDS_TO_CHECK = [
    "symbol", "exchange", "amount_thb", "order_type", "exchange_rate",
    "amount_usd", "order_id", "foreign_securities_account",
    "payment_reference", "receiving_account", "receiving_reference",
]

for fname in FILES:
    path = f"Test_Original/{fname}"
    print(f"\n=== {fname} ===")
    try:
        # preprocess=False: tall screenshot images hang under
        # zone-based preprocessing (see phase4_item1 notes)
        text = ocr_image_to_text(path, preprocess=False)
    except FileNotFoundError:
        print("  FILE NOT FOUND, skipping")
        continue

    doc_type = classify_document(text)
    print(f"  classify_document -> {doc_type}")

    if doc_type != "stock_confirmation":
        print(f"  MISCLASSIFIED (expected stock_confirmation)")
        continue

    parsed = parse_stock_confirmation_text(text)
    missing = [f for f in FIELDS_TO_CHECK if parsed.get(f) is None]
    if missing:
        print(f"  MISSING FIELDS: {missing}")
    else:
        print("  all core fields extracted OK")
    print(f"  symbol={parsed['symbol']} amount_thb={parsed['amount_thb']} order_id={parsed['order_id']}")
