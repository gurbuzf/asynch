"""The example scripts of examples/python run and give the results their comments promise."""
import os
import re
import sys
import unittest

import helpers


@helpers.requires_library
class TestExampleScripts(helpers.InExamples):

    def run_script(self, name, *args):
        code = "import sys, runpy; sys.argv = %r; runpy.run_path(%r, run_name='__main__')" % (
            [name] + list(args), os.path.join(self.dir, "python", name))
        proc = helpers.run_python(code, self.dir)
        self.assertEqual(proc.returncode, 0, proc.stdout)
        return proc.stdout

    def test_run_example(self):
        out = self.run_script("run_example.py")
        self.assertIn("test_2015.gbl: model 190, 11 links, 300 minutes", out)
        self.assertRegex(out, r"\n80\s+1\.936")                  # largest peak at the outlet

    def test_sensitivity(self):
        out = self.run_script("sensitivity.py")
        peaks = [float(m) for m in re.findall(r"^\d\.\d\d\s+([\d.]+)", out, re.M)]
        self.assertEqual(len(peaks), 4)
        self.assertEqual(peaks, sorted(peaks))                   # more runoff, higher peak
        self.assertIn("0.33                   1.9363", out)      # the value of test_2015.gbl

    @helpers.requires_compiler
    def test_custom_model(self):
        out = self.run_script("custom_model.py")
        self.assertIn("custom model vs built-in model 191: identical", out)
        self.assertTrue(os.path.exists("out_2015/custom.csv"))
        with open("out_2015/custom.pea") as f:
            lines = f.read().split("\n")
        self.assertEqual(lines[3].split()[0], "2")               # NewClassic writes 2 * link id

    @helpers.requires_compiler
    def test_new_network(self):
        out = self.run_script("new_network.py", os.path.join(self.tmp, "chain"))
        m = re.search(r"at 60 min: ([\d.]+) m3/s \(exact ([\d.]+)\)", out)
        self.assertIsNotNone(m, out)
        self.assertAlmostEqual(float(m.group(1)), float(m.group(2)), places=7)


if __name__ == "__main__":
    unittest.main()
