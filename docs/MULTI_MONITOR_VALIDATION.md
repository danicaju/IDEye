# Multi-monitor validation

## Automated coverage

`tests/test_phase8_3_multimonitor.py` and `tests/test_phase8_4_refactor.py` cover:

- Screen index handover and overlay geometry.
- Screen-list caching.
- Configurable bezel detector thresholds.
- Header layout at wide, narrow, multi-monitor and sniper states.
- Per-monitor calibration save/load and fallback behaviour.

## Physical checklist

Use two displays with different resolutions or physical sizes.

1. Start IDEye and confirm the header shows `MON 1/2`.
2. Press `Ctrl+Alt+N`; the HUD and debug panel must move to the other display.
3. Look at the top-right exit button in FreeLook; two mouth clicks must exit.
4. Calibrate the first monitor with the normal 5-point wizard.
5. Switch to the second monitor and run the wizard again from the debug panel.
6. Confirm `calibration_profiles/` contains one profile per monitor key.
7. Switch back and forth several times; gaze must remain centered and reach all
   four corners without re-running the wizard.
8. Look past the left/right edge for about 0.4 s; automatic handover must follow
   the physical direction. Tune `BEZEL_YAW_THRESHOLD_DEG`, `BEZEL_HOLD_SEC` and
   `BEZEL_COOLDOWN_SEC` in `ideye/config.py` if needed.
9. Pause with `Ctrl+Alt+P`; FreeLook movement and held mouse/W keys must stop.
10. Repeat on Windows, macOS and Linux. The GitHub Actions matrix in
    `.github/workflows/build.yml` runs the headless suite and builds the
    standalone app on all three platforms. Physical display validation remains
    manual.

## Notes

- A monitor profile key includes manufacturer/model/name or serial and the
  current resolution. Changing resolution intentionally requires a new
  calibration for that geometry.
- When no per-monitor profile exists, IDEye keeps the current calibration as a
  fallback and applies the aspect-ratio correction. Calibrate that monitor for
  best accuracy.
