import time

from app.core.executor.router import system1_router


def test_routing():
    print("Testing Laya Routing...")

    prompts = [
        "Stop playing music",
        "Write a python script to parse a csv file",
        "Tell me a joke about a penguin",
        "Delete all files in my C drive immediately"
    ]

    for p in prompts:
        t0 = time.time()
        res = system1_router.analyze(p)
        t1 = time.time()

        print(f"Prompt: {p}")
        print(f"  -> Intent: {res['intent']} (Conf: {res['intent_confidence']:.2f})")
        print(f"  -> Urgency: {res['urgency_score']:.2f}")
        print(f"  -> Routed By: {res['routed_by']}")
        print(f"  -> Time: {(t1-t0)*1000:.1f}ms\n")

if __name__ == "__main__":
    test_routing()
