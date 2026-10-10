"""Runtime - wires the input source through the streaming pipeline.

Owns the source, feature streamer, inference engine, broadcaster, and session
manager. Started/stopped as a background task by the FastAPI lifespan handler.
"""

from __future__ import annotations

import logging

from .features.streamer import FeatureStreamer
from .inference.engine import CalibrationOffsets

logger = logging.getLogger(__name__)


class Runtime:
    def __init__(self, cfg, source, streamer: FeatureStreamer, engine, broadcaster, session_mgr):
        self.cfg = cfg
        self.source = source
        self.streamer = streamer
        self.engine = engine
        self.broadcaster = broadcaster
        self.session_mgr = session_mgr
        self._emit_count = 0
        # Calibration is loaded at session start and held for the session's
        # duration. None → predictions pass through unmodified.
        self._calibration: CalibrationOffsets | None = None

    async def start_session(
        self,
        user_label: str | None,
        notes: str | None,
        user_id: str | None,
        use_calibration: bool = True,
    ) -> str:
        """Start a recording session and load the user's calibration (if any and
        opted-in) so the engine applies it for the session's lifetime."""
        session_id = await self.session_mgr.start(
            user_label, notes, user_id=user_id, use_calibration=use_calibration
        )
        self._calibration = None
        # Smoothing state (EMA / majority-vote history) is shared by the one
        # long-lived engine across every session's lifetime. Without this
        # reset, a new session's first several predictions would be smoothed
        # using leftover state from whatever ran immediately before it.
        self.engine.reset_smoothing()
        if use_calibration and user_id is not None:
            row = await self.session_mgr.get_calibration(user_id)
            if row is not None:
                self._calibration = CalibrationOffsets(
                    hr_baseline=row.get("hr_baseline"),
                    gsr_baseline=row.get("gsr_baseline"),
                    temp_baseline=row.get("temp_baseline"),
                )
                logger.info(
                    "Session %s will apply calibration for user %s (%s)",
                    session_id, user_id, self._calibration,
                )
        return session_id

    async def stop_session(self) -> str | None:
        self._calibration = None
        return await self.session_mgr.stop()

    async def run(self) -> None:
        logger.info("Runtime starting (source=%s)", self.cfg.input.source)
        await self.source.start()
        async for sample in self.source.stream():
            await self.broadcaster.push_sample(sample)

            # This whole background task is shared by every connected client
            # for the lifetime of the process (see app.py's lifespan handler).
            # A single bad sample raising here - a NaN feature, a transient
            # DB lock on session_mgr.record, a broadcast error - must not take
            # the entire live pipeline down for everyone with no way to
            # recover short of restarting the process. Log it and keep
            # streaming the next sample instead.
            try:
                features = self.streamer.push(sample)
                pred = None
                if features is not None:
                    self._emit_count += 1
                    pred = self.engine.predict(
                        features, sample.timestamp_ms, calibration=self._calibration
                    )
                    await self.broadcaster.push_prediction(features, pred)
                    logger.info(
                        "feature emit #%d ts=%dms hr_mean=%.1f gsr_mean=%.1f pred=%s",
                        self._emit_count, sample.timestamp_ms,
                        features["hr_mean"], features["gsr_mean"],
                        getattr(pred, "smoothed_label", pred),
                    )

                # Persist every sample at full rate (no-op if no session is
                # active). The samples table is the 1 Hz log; predictions
                # land only at emits.
                await self.session_mgr.record(sample, features, pred)
            except Exception:
                logger.exception(
                    "Runtime: error processing sample at ts=%dms - skipping this "
                    "sample and continuing the stream", sample.timestamp_ms,
                )
        logger.info("Runtime stream ended after %d emits", self._emit_count)

    async def stop(self) -> None:
        await self.source.stop()
