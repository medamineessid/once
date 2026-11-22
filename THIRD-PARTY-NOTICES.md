# THIRD-PARTY-NOTICES.md — desktop automation engine

Portions from microsoft/skill-recorder, MIT License, Copyright Microsoft Corporation.

This notice is for the desktop automation MVP analysis only. The reference repo
was read-only. No file was copied from it; the only output of the consultation
is the reuse decision record in REUSE.md. The MIT text is reproduced below so the
notice is self-contained.

## microsoft/skill-recorder

- Source: microsoft/skill-recorder (MIT)
- Reference copy used for analysis only:
  `C:\Users\DELL\AppData\Local\SkillRecorder\versions\505c97ae47be5642c0e1b44ebb8d1c1530c298fa`
- Use in this repository: conceptual analysis for the desktop MVP, plus the
  recording-analysis prompt in `ai/analyze_recording.py`. The prompt writer
  was consulted against the licensed reference file
  `electron/describer/instructions.ts` and adapts its method — event-first
  reconstruction of a short recording, grounding every step in captured
  signals in past tense, an exact structured-output contract, and "output
  only the schema, no prose" discipline — to Once's own engine step kinds and
  validation boundaries. No code was copied and no prompt is reproduced
  verbatim.

## MIT License

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
