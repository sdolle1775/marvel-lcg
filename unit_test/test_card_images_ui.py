from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


ROOT = Path(__file__).resolve().parents[1]


class TestCardImagesUI(unittest.TestCase):
    def test_placeholders_recover_without_reloading_the_page(self):
        node = shutil.which('node')
        compiler = shutil.which('tsc.cmd') or shutil.which('tsc')
        if not node or not compiler:
            self.skipTest('Node and TypeScript are required for the client regression')
        with tempfile.TemporaryDirectory(prefix='marvel-card-images-') as output:
            compiled = subprocess.run(
                [compiler, '-p', str(ROOT / 'public/js/tsconfig.json'), '--outDir', output],
                cwd=ROOT, capture_output=True, text=True, timeout=60,
            )
            self.assertEqual(compiled.returncode, 0, compiled.stdout + compiled.stderr)
            checked = subprocess.run(
                [node, str(ROOT / 'unit_test/card_images_ui.cjs'), str(Path(output) / 'module/card_images.js')],
                cwd=ROOT, capture_output=True, text=True, timeout=30,
            )
            self.assertEqual(checked.returncode, 0, checked.stdout + checked.stderr)


if __name__ == '__main__':
    unittest.main()
