import tempfile
import unittest
from pathlib import Path

import numpy as np

from ensure6g.thermal_data import (
    DEMO_EVENT_TICK,
    P2PRO_SOURCE,
    SYNTHETIC_SOURCE,
    current_thermal_stats,
    list_p2pro_frames,
    p2pro_preview_path,
    recommended_action,
    resolve_thermal_source,
    risk_label,
    semantic_event_from_stats,
    thermal_frame_stats,
)


def _write_p2pro_frame(path, temp_c):
    encoded = np.rint((np.asarray(temp_c, dtype=float) + 273.2) * 64).astype(np.int32)
    np.save(path, encoded)


class ThermalDataTests(unittest.TestCase):
    def setUp(self):
        list_p2pro_frames.clear()
        thermal_frame_stats.clear()

    def test_list_p2pro_frames_sorts_by_numeric_suffix(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            for name in ["frame_10.npy", "frame_2.npy", "frame_1.npy"]:
                _write_p2pro_frame(root / name, np.full((2, 2), 25.0))

            names = [Path(path).name for path in list_p2pro_frames(root)]

        self.assertEqual(names, ["frame_1.npy", "frame_2.npy", "frame_10.npy"])

    def test_stats_convert_p2pro_raw_units_to_celsius(self):
        with tempfile.TemporaryDirectory() as tmp:
            frame_path = Path(tmp) / "frame_330.npy"
            _write_p2pro_frame(frame_path, [[30.0, 31.0], [32.0, 40.0]])

            stats = thermal_frame_stats(frame_path)

        self.assertEqual(stats["frame_id"], 330)
        self.assertEqual(stats["shape"], (2, 2))
        self.assertEqual(stats["payload_bytes"], 16)
        self.assertAlmostEqual(stats["max_temp_c"], 40.0, places=1)
        self.assertEqual((stats["hotspot_x"], stats["hotspot_y"]), (1, 1))

    def test_p2pro_preview_path_maps_matching_png(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            frame_dir = root / "p2pro"
            preview_dir = root / "p2proPic"
            frame_dir.mkdir()
            preview_dir.mkdir()
            frame_path = frame_dir / "p2img00330.npy"
            preview_path = preview_dir / "p2img00330.png"
            _write_p2pro_frame(frame_path, np.full((2, 2), 25.0))
            preview_path.write_bytes(b"png")

            self.assertEqual(p2pro_preview_path(frame_path), str(preview_path))

    def test_semantic_high_risk_event_recommends_tsr(self):
        stats = {
            "frame_id": 330,
            "risk_label": risk_label(mean_temp_c=33.0, p99_temp_c=36.5, delta_temp_c=3.5),
            "mean_temp_c": 33.0,
            "p99_temp_c": 36.5,
            "delta_temp_c": 3.5,
        }

        event = semantic_event_from_stats(stats, sensor_id="S07")

        self.assertEqual(event["sensor_id"], "S07")
        self.assertEqual(event["risk_label"], "high")
        self.assertEqual(event["recommended_action"], "issue_tsr")
        self.assertGreaterEqual(event["confidence"], 0.70)
        self.assertEqual(recommended_action("high"), "issue_tsr")

    def test_missing_collected_data_resolves_to_synthetic(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(resolve_thermal_source(P2PRO_SOURCE, tmp), SYNTHETIC_SOURCE)

    def test_current_thermal_stats_reports_missing_data_fallback(self):
        with tempfile.TemporaryDirectory() as tmp:
            stats = current_thermal_stats(P2PRO_SOURCE, DEMO_EVENT_TICK, root_dir=tmp)

        self.assertFalse(stats["available"])
        self.assertTrue(stats["fallback_active"])
        self.assertEqual(stats["requested_source"], P2PRO_SOURCE)


if __name__ == "__main__":
    unittest.main()
