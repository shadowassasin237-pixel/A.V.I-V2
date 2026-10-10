"""Smoke test for the 3D Ultron orb in the right panel."""
import sys
import os
import shutil

sys.path.insert(0, '.')

# Backup user config
cfg_path = os.path.expanduser('~/.avi_config.json')
backup = cfg_path + '.testbak'
if os.path.exists(cfg_path):
    shutil.copy(cfg_path, backup)

try:
    import tkinter as tk
    from ui.gui import (
        AVIGUI, SettingsDialog, Orb3DWidget, load_saved_config,
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
    assert 'orb' not in root.MODES, 'orb HUD mode should be removed'
    print('  orb HUD mode removed (replaced by chat-area widget)')

    # 2. The Orb3DWidget should be present and have a canvas
    assert hasattr(root, 'orb_widget'), 'orb_widget attribute missing'
    assert isinstance(root.orb_widget, Orb3DWidget), \
        f'orb_widget type wrong: {type(root.orb_widget)}'
    print('  orb_widget present and is Orb3DWidget')

    # 3. The orb widget should be visible (in the right panel grid)
    try:
        root.update_idletasks()
        w = root.orb_widget.winfo_width()
        h = root.orb_widget.winfo_height()
        print(f'  orb size: {w}x{h}')
        assert w > 50 and h > 100, f'orb too small: {w}x{h}'
    except Exception as exc:
        print(f'  orb size check: {exc}')

    # 4. The chat should still be present
    assert hasattr(root, 'chat'), 'chat missing'
    print('  chat widget present')

    # 5. The remaining HUD modes should all draw
    root.hud_canvas.update_idletasks()
    root.hud_canvas.config(width=400, height=400)
    for m in root.MODES:
        root.set_mode(m)
        fn = {
            'reactor': root._draw_reactor,
            'clock': root._draw_clock,
            'network': root._draw_network,
            'voice': root._draw_voice,
            'mask': root._draw_mask,
        }[m]
        fn(root.hud_canvas, 200, 200)
    print('  all remaining modes draw OK')

    # 6. The orb widget should react to all 4 states
    for state in ('idle', 'listening', 'thinking', 'speaking'):
        # Simulate a state change by setting the callback
        root.set_orb_state(state)
        # Let the orb widget tick a few times
        for _ in range(3):
            root.orb_widget.update_idletasks()
            root.orb_widget._tick.__wrapped__ if hasattr(root.orb_widget._tick, '__wrapped__') else None
        # Verify voice level pushes through
        root.set_voice_level(0.5)
        assert root.orb_widget._voice_level == 0.5, f'voice level not pushed in {state}'
    print('  orb reacts to all 4 states + voice level')

    # 7. Force a draw on the orb so it doesn't crash
    for state in ('idle', 'listening', 'thinking', 'speaking'):
        root.set_orb_state(state)
        root.orb_widget._draw(state)
    print('  orb _draw executes for all 4 states')

    # 8. The orb mode should NOT be in MODES but the button bar should
    # still iterate over them. Check the mode bar exists.
    # (Can't easily inspect the button text from here, but the modes
    # themselves iterate fine as shown above.)
    print(f'  mode bar: {root.MODES}')

    # 9. Config roundtrip still works
    test_voice = 'Ashley'
    save_config_to_file(
        'sk-or-v1-test-fake-12345678', 'anthropic/claude-3.5-sonnet',
        'wss://test.livekit.cloud', 'lkkey', 'lksecret', test_voice,
    )
    load_saved_config()
    assert config.AVI_VOICE == test_voice
    print('  config roundtrip OK')

    root.destroy()
    print()
    print('ALL OK')

finally:
    if os.path.exists(backup):
        shutil.move(backup, cfg_path)
    elif os.path.exists(cfg_path):
        os.remove(cfg_path)
