import sys, glob, re, importlib.util
VN = (" NOT cartoon, NOT 3D render, no heavy gradients, no clutter that breaks the style, no watermark. "
      "16:9, ultra-detailed. All people are Vietnamese, all settings and signage are Vietnamese. "
      "No English text unless it is part of a real brand name or proper noun identified in the subject survey. "
      "No generic text unless a Vietnamese label is specified above.")
US = (" NOT cartoon, NOT 3D render, no heavy gradients, no clutter that breaks the style, no watermark. "
      "16:9, ultra-detailed. This scene is set in the United States as stated in the script, people are American. "
      "No text except the real brand names, proper nouns or Vietnamese labels written above.")
JP = (" NOT cartoon, NOT 3D render, no heavy gradients, no clutter that breaks the style, no watermark. "
      "16:9, ultra-detailed. This scene is set in Japan as stated in the script, people are as described above. "
      "No text except the Vietnamese labels or real proper nouns written above.")
LOCK = {"VN": VN, "US": US, "JP": JP}
lines = open('scripts/vien-duong-lao-voiceover-lines.txt', encoding='utf-8').read().splitlines()
P = {}
for f in sorted(glob.glob('scripts/_prompts/batch*.py')):
    spec = importlib.util.spec_from_file_location(f, f); m = importlib.util.module_from_spec(spec); spec.loader.exec_module(m)
    for n, tag, text in m.PROMPTS:
        assert n not in P, f"duplicate {n}"
        P[n] = (tag, text)
nums = sorted(P)
assert nums == list(range(1, len(nums)+1)), f"gap in numbering: {sorted(set(range(1,max(nums)+1))-set(nums))}"
out = [f"{n:03d}. Vox-style editorial collage, {P[n][1].strip().rstrip(".")}.{LOCK[P[n][0]]}" for n in nums]
open('scripts/vien-duong-lao-image-prompts.txt', 'w', encoding='utf-8').write('\n'.join(out) + '\n')
print(f"{len(out)} prompts built / {len(lines)} voiceover lines")
