"""Phase 2 real-time inference service.

Subpackages:
  config         - service.yaml → typed ServiceConfig
  app            - FastAPI app factory + lifespan
  logging_setup  - stdlib logging configuration
  runtime        - wires source → streamer → engine → broadcaster → sessions
  sources        - input source abstraction (csv_replay | serial | tcp)
  features       - streaming feature extractor
  inference      - model loading + prediction + smoothing
  ws             - WebSocket broadcaster + REST control routes
  sessions       - SQLite persistence + export
"""
