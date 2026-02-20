"""
Standalone utility to generate low/high confidence match bounds for a joint length.

Defaults:
    - Difference ratio tolerance: 20% (0.20)
    - Confidence threshold: 80% (0.80)

Confidence model:
    confidence = 1 - (difference_ratio / tolerance)

Where difference_ratio = abs(candidate_length - joint_length) / joint_length

Given a confidence threshold (e.g., 0.80), the high-confidence maximum
difference ratio is:
    high_conf_ratio = tolerance * (1 - confidence_threshold)

This yields:
    - High-confidence range (narrow, centered on joint length)
    - Low-confidence edge bands (within tolerance, but below threshold)
    - Overall tolerated range

Usage examples:
    python joint_length_confidence_tool.py --joint-length 12.0
    python joint_length_confidence_tool.py --joint-length 12.0 --tolerance 25 --confidence-threshold 85
"""

from __future__ import annotations

import argparse
import tkinter as tk
from tkinter import messagebox


DEFAULT_TOLERANCE_PERCENT = 20.0
DEFAULT_CONFIDENCE_THRESHOLD_PERCENT = 80.0


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate low/high confidence length bounds from joint length, tolerance, and confidence threshold."
    )
    parser.add_argument(
        "--joint-length",
        type=float,
        help="Reference joint length (must be > 0).",
    )
    parser.add_argument(
        "--tolerance",
        type=float,
        default=DEFAULT_TOLERANCE_PERCENT,
        help="Difference ratio tolerance as a percent (default: 20).",
    )
    parser.add_argument(
        "--confidence-threshold",
        type=float,
        default=DEFAULT_CONFIDENCE_THRESHOLD_PERCENT,
        help="Confidence threshold as a percent from 0 to 100 (default: 80).",
    )
    parser.add_argument(
        "--ui",
        action="store_true",
        help="Launch a simple graphical UI.",
    )
    return parser.parse_args()


def _validate_inputs(joint_length: float, tolerance_pct: float, confidence_threshold_pct: float) -> None:
    if joint_length <= 0:
        raise ValueError("Joint length must be greater than 0.")
    if tolerance_pct <= 0:
        raise ValueError("Tolerance percent must be greater than 0.")
    if not 0 <= confidence_threshold_pct <= 100:
        raise ValueError("Confidence threshold percent must be between 0 and 100.")


def _compute_bounds(joint_length: float, tolerance_pct: float, confidence_threshold_pct: float) -> dict[str, float]:
    tolerance_ratio = tolerance_pct / 100.0
    confidence_threshold = confidence_threshold_pct / 100.0

    # Overall accepted difference ratio (max allowed by tolerance)
    overall_half_width_ratio = tolerance_ratio

    # Difference ratio that still meets "high confidence"
    high_half_width_ratio = tolerance_ratio * (1.0 - confidence_threshold)

    overall_lower = joint_length * (1.0 - overall_half_width_ratio)
    overall_upper = joint_length * (1.0 + overall_half_width_ratio)

    high_lower = joint_length * (1.0 - high_half_width_ratio)
    high_upper = joint_length * (1.0 + high_half_width_ratio)

    return {
        "joint_length": joint_length,
        "tolerance_pct": tolerance_pct,
        "confidence_threshold_pct": confidence_threshold_pct,
        "overall_lower": overall_lower,
        "overall_upper": overall_upper,
        "high_lower": high_lower,
        "high_upper": high_upper,
    }


def _build_report_text(bounds: dict[str, float]) -> str:
    joint_length = bounds["joint_length"]
    tolerance_pct = bounds["tolerance_pct"]
    confidence_threshold_pct = bounds["confidence_threshold_pct"]

    overall_lower = bounds["overall_lower"]
    overall_upper = bounds["overall_upper"]
    high_lower = bounds["high_lower"]
    high_upper = bounds["high_upper"]

    return "\n".join(
        [
            "=" * 72,
            "JOINT LENGTH CONFIDENCE RANGE TOOL",
            "=" * 72,
            f"Joint length:               {joint_length:.6f}",
            f"Difference tolerance (%):   {tolerance_pct:.2f}",
            f"Confidence threshold (%):   {confidence_threshold_pct:.2f}",
            "-" * 72,
            "HIGH CONFIDENCE RANGE (>= threshold)",
            f"  Lower bound:              {high_lower:.6f}",
            f"  Upper bound:              {high_upper:.6f}",
            "-",
            "LOW CONFIDENCE RANGE (< threshold, but within tolerance)",
            "  Lower side band:",
            f"    {overall_lower:.6f}  to  {high_lower:.6f}",
            "  Upper side band:",
            f"    {high_upper:.6f}  to  {overall_upper:.6f}",
            "-",
            "OVERALL TOLERATED RANGE",
            f"  Lower bound:              {overall_lower:.6f}",
            f"  Upper bound:              {overall_upper:.6f}",
            "=" * 72,
        ]
    )


def _print_report(bounds: dict[str, float]) -> None:
    print(_build_report_text(bounds))


def _launch_ui() -> None:
    root = tk.Tk()
    root.title("Joint Length Confidence Tool")
    root.geometry("820x540")

    frame = tk.Frame(root, padx=12, pady=12)
    frame.pack(fill="both", expand=True)

    tk.Label(frame, text="Joint Length:").grid(row=0, column=0, sticky="w", pady=(0, 8))
    joint_entry = tk.Entry(frame, width=20)
    joint_entry.grid(row=0, column=1, sticky="w", pady=(0, 8))

    tk.Label(frame, text="Difference Tolerance (%):").grid(row=1, column=0, sticky="w", pady=(0, 8))
    tolerance_entry = tk.Entry(frame, width=20)
    tolerance_entry.insert(0, str(DEFAULT_TOLERANCE_PERCENT))
    tolerance_entry.grid(row=1, column=1, sticky="w", pady=(0, 8))

    tk.Label(frame, text="Confidence Threshold (%):").grid(row=2, column=0, sticky="w", pady=(0, 8))
    confidence_entry = tk.Entry(frame, width=20)
    confidence_entry.insert(0, str(DEFAULT_CONFIDENCE_THRESHOLD_PERCENT))
    confidence_entry.grid(row=2, column=1, sticky="w", pady=(0, 8))

    output_box = tk.Text(frame, height=20, width=98, wrap="none")
    output_box.grid(row=4, column=0, columnspan=3, sticky="nsew", pady=(10, 0))

    def on_calculate() -> None:
        try:
            joint_length = float(joint_entry.get())
            tolerance_pct = float(tolerance_entry.get())
            confidence_threshold_pct = float(confidence_entry.get())

            _validate_inputs(joint_length, tolerance_pct, confidence_threshold_pct)
            bounds = _compute_bounds(joint_length, tolerance_pct, confidence_threshold_pct)
            report = _build_report_text(bounds)

            output_box.delete("1.0", tk.END)
            output_box.insert(tk.END, report)
        except ValueError as exc:
            messagebox.showerror("Input Error", str(exc))

    calculate_btn = tk.Button(frame, text="Calculate Ranges", command=on_calculate)
    calculate_btn.grid(row=3, column=0, columnspan=2, sticky="w")

    frame.columnconfigure(2, weight=1)
    frame.rowconfigure(4, weight=1)
    root.mainloop()


def main() -> int:
    args = _parse_args()

    try:
        if args.ui:
            _launch_ui()
            return 0

        if args.joint_length is None:
            raise ValueError("--joint-length is required when not using --ui.")

        _validate_inputs(args.joint_length, args.tolerance, args.confidence_threshold)
        bounds = _compute_bounds(args.joint_length, args.tolerance, args.confidence_threshold)
        _print_report(bounds)
        return 0
    except ValueError as exc:
        print(f"Input error: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

