"""Figure / table / scan evidence: classify generically, never invent boxes."""

from __future__ import annotations

import unittest

from evidence_mapping import SOURCE_NATIVE, SOURCE_NONE, infer_content_type
from visual_evidence import apply_visual_highlight_policy, quote_regions_are_safe


def _payload(**overrides):
    base = {
        "content_type": "native_text",
        "highlight_available": True,
        "quote_highlight_available": False,
        "quote_regions": [],
        "quote_mapping_status": "none",
        "regions": [
            {
                "page": 1,
                "x0": 40.0,
                "y0": 80.0,
                "x1": 520.0,
                "y1": 700.0,
                "coord_space": "pdf",
            }
        ],
    }
    base.update(overrides)
    return base


class TestInferContentType(unittest.TestCase):
    def test_figure_labels_are_generic(self):
        for text in (
            "Figure 2. Overview of the pipeline.",
            "Fig. 3 Schematic of the encoder.",
            "Illustration 1. System architecture.",
            "Plate 4 stained section.",
            "Diagram 5 data flow.",
        ):
            self.assertEqual(
                infer_content_type(
                    text,
                    highlight_available=True,
                    layout_source=SOURCE_NATIVE,
                ),
                "figure_caption",
                msg=text,
            )

    def test_long_body_text_mentioning_a_figure_stays_native(self):
        text = (
            "The results in figure 2 of the appendix are consistent with the "
            "main experiment, which used labeled examples and a held-out test "
            "split. Accuracy improved after regularization was added to the "
            "training objective, and the authors discuss failure modes at length "
            "along with several follow-up ablations on the validation split."
        )
        self.assertGreaterEqual(len(text), 280)
        self.assertEqual(
            infer_content_type(
                text,
                highlight_available=True,
                layout_source=SOURCE_NATIVE,
            ),
            "native_text",
        )

    def test_table_labels_and_grid_markup(self):
        self.assertEqual(
            infer_content_type(
                "Table 1. Hyperparameters used in training.",
                highlight_available=True,
                layout_source=SOURCE_NATIVE,
            ),
            "table",
        )
        self.assertEqual(
            infer_content_type(
                "Name | Value | Unit |\nA | 1 | s |\nB | 2 | m",
                highlight_available=True,
                layout_source=SOURCE_NATIVE,
            ),
            "table",
        )

    def test_scans_without_native_layout(self):
        self.assertEqual(
            infer_content_type(
                "blurry page",
                highlight_available=False,
                layout_source=SOURCE_NONE,
            ),
            "scanned_or_image",
        )
        self.assertEqual(
            infer_content_type(
                "blurry page",
                highlight_available=False,
                layout_source=SOURCE_NONE,
                text_engine="tesseract-ocr",
            ),
            "scanned_ocr",
        )

    def test_image_heavy_low_text_page_is_a_scan_not_a_figure(self):
        self.assertEqual(
            infer_content_type(
                "logo",
                highlight_available=False,
                layout_source=SOURCE_NATIVE,
                image_count=2,
                span_count=3,
            ),
            "scanned_or_image",
        )

    def test_a_logo_on_a_text_page_is_not_a_figure(self):
        self.assertEqual(
            infer_content_type(
                "Supervised learning uses labeled examples for classification.",
                highlight_available=True,
                layout_source=SOURCE_NATIVE,
                image_count=1,
                span_count=40,
            ),
            "native_text",
        )


class TestVisualHighlightPolicy(unittest.TestCase):
    def test_native_text_is_unchanged(self):
        payload = _payload(quote_highlight_available=True, quote_regions=[{"page": 1, "x0": 10, "y0": 20, "x1": 80, "y1": 36}])
        out = apply_visual_highlight_policy(payload)
        self.assertTrue(out["highlight_available"])
        self.assertTrue(out["quote_highlight_available"])
        self.assertEqual(len(out["quote_regions"]), 1)

    def test_scans_never_paint(self):
        payload = _payload(
            content_type="scanned_or_image",
            quote_highlight_available=True,
            quote_mapping_status="exact",
            quote_regions=[{"page": 1, "x0": 10, "y0": 20, "x1": 80, "y1": 36}],
        )
        out = apply_visual_highlight_policy(payload)
        self.assertFalse(out["highlight_available"])
        self.assertFalse(out["quote_highlight_available"])
        self.assertEqual(out["quote_regions"], [])
        self.assertEqual(out["quote_mapping_status"], "no_layout")

    def test_scan_without_boxes_keeps_localization_status(self):
        out = apply_visual_highlight_policy(
            _payload(
                content_type="scanned_or_image",
                highlight_available=False,
                quote_highlight_available=False,
                quote_regions=[],
                quote_mapping_status="sentence",
            )
        )
        self.assertFalse(out["highlight_available"])
        self.assertEqual(out["quote_mapping_status"], "sentence")

    def test_figure_keeps_tight_caption_box(self):
        caption = [{"page": 3, "x0": 72.0, "y0": 640.0, "x1": 480.0, "y1": 656.0}]
        self.assertTrue(quote_regions_are_safe("figure_caption", caption))
        out = apply_visual_highlight_policy(
            _payload(
                content_type="figure_caption",
                quote_highlight_available=True,
                quote_mapping_status="exact",
                quote_regions=caption,
            )
        )
        self.assertFalse(out["highlight_available"])
        self.assertTrue(out["quote_highlight_available"])
        self.assertEqual(len(out["quote_regions"]), 1)

    def test_figure_strips_boxes_that_cover_the_graphic(self):
        huge = [{"page": 3, "x0": 40.0, "y0": 80.0, "x1": 560.0, "y1": 720.0}]
        self.assertFalse(quote_regions_are_safe("figure_caption", huge))
        out = apply_visual_highlight_policy(
            _payload(
                content_type="figure_caption",
                quote_highlight_available=True,
                quote_mapping_status="exact",
                quote_regions=huge,
            )
        )
        self.assertFalse(out["highlight_available"])
        self.assertFalse(out["quote_highlight_available"])
        self.assertEqual(out["quote_regions"], [])
        self.assertEqual(out["quote_mapping_status"], "fallback_chunk")

    def test_table_strips_near_full_page_boxes(self):
        huge = [{"page": 2, "x0": 36.0, "y0": 72.0, "x1": 576.0, "y1": 720.0}]
        out = apply_visual_highlight_policy(
            _payload(
                content_type="table",
                quote_highlight_available=True,
                quote_mapping_status="normalized",
                quote_regions=huge,
            ),
            page_width=612.0,
            page_height=792.0,
        )
        self.assertFalse(out["highlight_available"])
        self.assertFalse(out["quote_highlight_available"])
        self.assertEqual(out["quote_mapping_status"], "fallback_chunk")

    def test_does_not_invent_geometry(self):
        out = apply_visual_highlight_policy(
            _payload(
                content_type="figure_caption",
                highlight_available=True,
                quote_highlight_available=False,
                quote_regions=[],
            )
        )
        self.assertFalse(out["highlight_available"])
        self.assertFalse(out["quote_highlight_available"])
        self.assertEqual(out["quote_regions"], [])


if __name__ == "__main__":
    unittest.main()
