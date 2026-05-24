"""
Template-driven synthetic data.

Cheap, deterministic, en/fr/rw. Output schema matches the live API so the
same record format works for training and for eval.

intent_corpus()   → iterator of {text, language, intent} dicts
"""
from __future__ import annotations

from itertools import product
from typing import Iterator

# ── Intent templates per language ────────────────────────────────────────────
# Each entry: (intent_label, [phrasings])

_EN = [
    ('start',    ['start', 'begin', 'launch', 'let us go', 'go ahead', 'play the demo', 'start training', "let's begin"]),
    ('next',     ['next', 'next step', 'continue', 'move on', 'skip', 'forward', 'next please', 'go to next']),
    ('pause',    ['pause', 'wait', 'hold on', 'hold up', 'pause please', 'stop a moment', 'one second']),
    ('resume',   ['resume', 'continue now', 'go on', 'keep going', 'pick it up', 'resume please']),
    ('restart',  ['restart', 'replay', 'again', 'from the start', 'from the beginning', 'one more time', 'do it again']),
    ('stop',     ['stop', 'halt', 'cancel', 'enough', 'end demo', 'stop training', 'exit']),
    ('greet',    ['hello', 'hi', 'hey', 'good morning', 'good afternoon', 'good evening', 'hi there']),
    ('wake',     ['jorinova', 'nexus', 'alis x', 'hey jorinova', 'ok nexus']),
    ('help',     ['help', 'what can you do', 'how do i use this', 'what are the commands', 'show commands']),
    ('thanks',   ['thanks', 'thank you', 'thanks a lot', 'much appreciated']),
]

_FR = [
    ('start',    ['démarrer', 'commencer', 'lancer la démo', 'allez-y', 'on commence', 'on y va']),
    ('next',     ['suivant', 'étape suivante', 'continue', 'passer à la suite', 'avancer']),
    ('pause',    ['pause', 'attends', 'attendez', 'un instant', 'une seconde']),
    ('resume',   ['reprendre', 'reprends', 'continue maintenant', 'on continue']),
    ('restart',  ['recommencer', 'rejouer', 'depuis le début', 'encore une fois']),
    ('stop',     ['arrête', 'arrêter', 'stop', 'annuler', 'terminer']),
    ('greet',    ['bonjour', 'bonsoir', 'salut', 'bonne matinée']),
    ('wake',     ['jorinova', 'nexus', 'alis x']),
    ('help',     ['aide', 'que peux-tu faire', 'quelles sont les commandes']),
    ('thanks',   ['merci', 'merci beaucoup']),
]

_RW = [
    ('start',    ['tangira', 'tangiriza', 'tangire demo', 'genda', 'genda mbere']),
    ('next',     ['komeza', 'intambwe ikurikira', 'soko ku ikurikira']),
    ('pause',    ['hagarara', 'tegereza', 'hagarara gato', 'tegerezako']),
    ('resume',   ['tangira nanone', 'komeza nanone', 'subira ukomeze']),
    ('restart',  ['subira', 'ongera utangire', 'ongera']),
    ('stop',     ['reka', 'hagarika', 'birangiye']),
    ('greet',    ['mwaramutse', 'mwiriwe', 'muraho', 'muraho neza']),
    ('wake',     ['jorinova', 'nexus', 'alis x']),
    ('help',     ['ubufasha', 'mbwira amategeko', 'wakora iki']),
    ('thanks',   ['murakoze', 'urakoze cyane']),
]


def intent_corpus() -> Iterator[dict]:
    """Yield {text, language, intent} for every (lang, template) pair, plus
    a few wake-then-command compositions which exercise the wake>greet
    precedence in the regex matcher."""
    for lang, table in (('en', _EN), ('fr', _FR), ('rw', _RW)):
        for intent, phrases in table:
            for p in phrases:
                yield {'text': p, 'language': lang, 'intent': intent}

    # Wake + greet compositions (wake > greet by design)
    for lang, hello in (('en', 'hello'), ('fr', 'bonjour'), ('rw', 'mwaramutse')):
        for wake in ('jorinova', 'nexus'):
            yield {'text': f'{hello} {wake}', 'language': lang, 'intent': 'greet'}
            yield {'text': f'{wake} {hello}', 'language': lang, 'intent': 'greet'}

    # Wake + command compositions (command wins over wake-only)
    for lang, cmd in (('en', 'next'), ('fr', 'suivant'), ('rw', 'komeza')):
        yield {'text': f'jorinova {cmd}', 'language': lang, 'intent': cmd_intent_for(cmd)}


def cmd_intent_for(cmd: str) -> str:
    m = {'next': 'next', 'suivant': 'next', 'komeza': 'next'}
    return m.get(cmd, 'unknown')


if __name__ == '__main__':
    import json, sys
    for row in intent_corpus():
        sys.stdout.write(json.dumps(row, ensure_ascii=False) + '\n')
