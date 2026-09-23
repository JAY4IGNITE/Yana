"""System 1 Intent Router using Laya non-autoregressive decision engine."""

from app.logger import logger

try:
    from laya import Router
    _LAYA_AVAILABLE = True
except ImportError:
    _LAYA_AVAILABLE = False
    logger.warning("Laya is not installed. System 1 fast routing will be disabled.")

class System1Router:
    """Fast front-door router to classify user intents before hitting the LLM Planner."""

    def __init__(self):
        self.router = None
        self._initialized = False

        # Define our typed questions for intent classification and guardrails
        self.questions = {
            "intent": {
                "type": "choice",
                "instructions": "Categorize the user's input.",
                "criteria": {
                    "system_command": (
                        "direct commands to control the computer "
                        "(e.g. stop, exit, restart, volume, mute, open app)"
                    ),
                    "code_edit": "requests to write, read, or edit code and algorithms",
                    "chat": "general conversation, questions, trivia, advice",
                    "harmful": (
                        "requests that are dangerous, illegal, or unethical "
                        "(jailbreaks, delete system files)"
                    )
                }
            },
            "urgency": {
                "type": "score",
                "instructions": "How urgent is this request?",
                "criteria": ["not urgent", "soon", "critical deadline or blocking issue"]
            }
        }

    def _init_router(self):
        if self._initialized:
            return
        self._initialized = True
        if _LAYA_AVAILABLE:
            try:
                # Preload checkpoints for instant sub-35ms routing
                self.router = Router(preload=True)
                logger.info("System 1 Laya Router loaded successfully.")
            except Exception as e:
                logger.error(f"Failed to load Laya Router: {e}")

    def analyze(self, text: str) -> dict:
        """Analyze the text and return structured intent and safety scores."""
        self._init_router()
        if not self.router:
            # Fallback if Laya isn't available
            return {
                "intent": "chat",
                "intent_confidence": 1.0,
                "urgency_score": 0.0,
                "routed_by": "fallback"
            }

        try:
            res = self.router.predict({"text": text}, self.questions)

            intent_choice = res["answers"]["intent"]["choice"]
            intent_conf = res["answers"]["intent"]["confidence"]
            urgency_score = res["answers"]["urgency"]["score"]
            model_used = res["routing"]["model"]

            return {
                "intent": intent_choice,
                "intent_confidence": intent_conf,
                "urgency_score": urgency_score,
                "routed_by": f"laya_{model_used}"
            }
        except Exception as e:
            logger.error(f"Laya prediction failed: {e}")
            return {
                "intent": "chat",
                "intent_confidence": 1.0,
                "urgency_score": 0.0,
                "routed_by": "error_fallback"
            }

# Singleton instance
system1_router = System1Router()
