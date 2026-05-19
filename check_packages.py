import importlib, sys
checks = [
    ('numpy',        lambda: importlib.import_module('numpy')),
    ('scipy',        lambda: importlib.import_module('scipy')),
    ('librosa',      lambda: importlib.import_module('librosa')),
    ('soundfile',    lambda: importlib.import_module('soundfile')),
    ('pyttsx3',      lambda: importlib.import_module('pyttsx3')),
    ('gtts',         lambda: __import__('gtts')),
    ('resemblyzer',  lambda: __import__('resemblyzer')),
]

ok = 0
fail = 0
for name, mod_fn in checks:
    try:
        mod = mod_fn()
        ver = getattr(mod, '__version__', 'loaded')
        print(f'[OK]   {name:15} -> {ver}')
        ok += 1
    except Exception as e:
        print(f'[FAIL] {name:15} -> {e}')
        fail += 1

print()
print(f'Summary: {ok} passed, {fail} failed')
if fail:
    sys.exit(1)
print("All packages functional.")
