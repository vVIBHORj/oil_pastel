import unittest

import cv2
import numpy as np

from oil_pastel_patches import OilPastelPainter


class PatchVisibilityTests(unittest.TestCase):
    def test_completed_patches_are_recorded_and_visible_on_overlay(self):
        image = np.full((48, 64, 3), 180, dtype=np.uint8)
        painter = OilPastelPainter(image, seed=7, density=0.1)

        painter.paint_patch(32, 24, {
            "name": "Test pass",
            "r": 0.1,
            "w": 0.026,
            "l": 0.08,
            "dens": 0.2,
            "src": 0,
            "edge_only": False,
        })

        clean = painter.render()
        overlay = painter.render(show_patches=True)

        self.assertEqual(len(painter.patches), 1)
        self.assertEqual(painter.patches[0]["number"], 1)
        self.assertFalse(np.array_equal(clean, overlay))

    def test_patch_map_has_same_dimensions_as_rendered_frame(self):
        image = np.full((48, 64, 3), 180, dtype=np.uint8)
        painter = OilPastelPainter(image, seed=7, density=0.1)

        patch_map = painter.render(show_patches=True)

        self.assertEqual(patch_map.shape, painter.render().shape)
        self.assertEqual(patch_map.dtype, np.uint8)


if __name__ == "__main__":
    unittest.main()
