"""Forwarding wrapper for scripts/test_gmail_inference.py."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from scripts.test_gmail_inference import run_inference_test

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="Test Gmail Priority Inference")
    parser.add_argument("--max-emails", type=int, default=20, help="Maximum number of emails to evaluate")
    parser.add_argument("--query", type=str, default=None, help="Optional Gmail search query filter")
    args = parser.parse_args()
    run_inference_test(max_emails=args.max_emails, query=args.query)
