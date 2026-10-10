"""Smoke test for the new GUI features."""
import sys
import os
import shutil

sys.path.insert(0, '.')
sys.path.insert(0, os.path.dirname(__file__))

# Backup the existing user config
cfg_path = os.path.expanduser('~/.avi_config.json')
backup = cfg_path + '.testbak'
if os.path.exists(cfg_path):
    shutil.copy(cfg_path, backup)

try:
    import tkinter as tk
    from ui.gui import (
        AVIGUI, SettingsDialog, load_saved_config,
        save_config_to_file, INWORLD_VOICES, POPULAR_MODELS,
    )
    from core.brain import AVIBrain
    import config

    class DummySpeaker:
        def speak(self, text):
            pass
        def stop(self):
            pass
        voice = 'Arjun'

    # 1. Build the GUI
    root = AVIGUI(
        brain=AVIBrain(api_key='', model='openai/gpt-4o-mini'),
        speaker=DummySpeaker(),
        agent_launcher=None,
    )
    print('GUI built OK')
    print('  MODES =', root.MODES)
    assert 'orb' in root.MODES, 'orb mode not registered'
    print('  orb mode in MODES')

    # 2. Config roundtrip
    test_key = 'sk-or-v1-test-fake-key-12345678'
    test_model = 'anthropic/claude-3.5-sonnet'
    test_voice = 'Priya'
    save_config_to_file(
        test_key, test_model,
        'wss://test.livekit.cloud', 'lkkey', 'lksecret', test_voice,
    )
    load_saved_config()
    assert config.OPENROUTER_API_KEY == test_key, 'key mismatch'
    assert config.LLM_MODEL == test_model, 'model mismatch'
    assert config.LIVEKIT_URL == 'wss://test.livekit.cloud', 'url mismatch'
    assert config.LIVEKIT_API_KEY == 'lkkey', 'lkkey mismatch'
    assert config.AVI_VOICE == test_voice, 'voice mismatch'
    assert os.environ.get('AVI_VOICE') == test_voice, 'env voice mismatch'
    print('  Config roundtrip OK (key/model/livekit/voice + os.environ)')

    # 3. Verify orb drawing function
    root.hud_canvas.update_idletasks()
    root.hud_canvas.config(width=400, height=400)
    root.set_mode('orb')
    root._draw_ultron_orb(root.hud_canvas, 200, 200)
    print('  orb draw OK')

    # 4. Other modes still work
    for m in ('reactor', 'clock', 'network', 'voice', 'mask'):
        root.set_mode(m)
        fn = {
            'reactor': root._draw_reactor,
            'orb': root._draw_ultron_orb,
            'clock': root._draw_clock,
            'network': root._draw_network,
            'voice': root._draw_voice,
            'mask': root._draw_mask,
        }[m]
        fn(root.hud_canvas, 200, 200)
    print('  all 6 modes draw OK')

    # 5. Speaker set_voice
    from voice.speaker import AVISpeaker
    sp = AVISpeaker.__new__(AVISpeaker)  # avoid LiveKit client init
    sp.voice = 'Mark'
    sp.set_voice('Ashley')
    assert sp.voice == 'Ashley', 'set_voice did not update'
    assert os.environ.get('AVI_VOICE') == 'Ashley', 'env not updated'
    print('  speaker.set_voice OK')

    root.destroy()
    print()
    print('ALL OK')

finally:
    # Restore original user config
    if os.path.exists(backup):
        shutil.move(backup, cfg_path)
    elif os.path.exists(cfg_path):
        os.remove(cfg_path)
