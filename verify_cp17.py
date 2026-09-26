from core.main import create_agent
from core.state import JobState


def check(name, fn):
    try:
        fn()
        print(f"[PASS] {name}")
        return True
    except Exception as exc:
        print(f"[FAIL] {name}: {exc}")
        return False


def test_registration():
    agent=create_agent()
    expected={"prompt_construct","text_generate","text_summarize","text_extract","text_classify","text_transform"}
    assert expected.issubset(set(agent.capabilities.list()))


def test_prompt():
    agent=create_agent()
    result=agent.tools.execute("prompt_construct",{"instruction":"Explain calculus","context":"BSc mathematics","constraints":["be concise"]})
    assert "Explain calculus" in result
    assert "BSc mathematics" in result
    assert "be concise" in result


def test_generation():
    agent=create_agent()
    result=agent.tools.execute("text_generate",{"prompt":"Hello JARVIS","max_length":100})
    assert result["text"]=="Hello JARVIS"
    assert result["provider"]=="local-placeholder"


def test_summary():
    agent=create_agent()
    result=agent.tools.execute("text_summarize",{"text":"First sentence. Second sentence. Third sentence.","max_sentences":2})
    assert result["summary"]=="First sentence. Second sentence."


def test_extract():
    agent=create_agent()
    result=agent.tools.execute("text_extract",{"text":"name: Alice, age: 20","fields":["name","age"]})
    assert result["fields"]["name"]=="Alice"
    assert result["fields"]["age"]=="20"


def test_classify():
    agent=create_agent()
    result=agent.tools.execute("text_classify",{"text":"mathematics calculus algebra","labels":["mathematics","history"]})
    assert result["label"]=="mathematics"


def test_transform():
    agent=create_agent()
    result=agent.tools.execute("text_transform",{"text":"  hello   jarvis  ","operation":"normalize_whitespace"})
    assert result["text"]=="hello jarvis"


def test_discovery():
    agent=create_agent()
    cases=[
        ("construct prompt","prompt_construct"),
        ("generate text","text_generate"),
        ("summarize text","text_summarize"),
        ("extract information","text_extract"),
        ("classify text","text_classify"),
        ("transform text","text_transform"),
    ]
    for query,expected in cases:
        matches=agent.capabilities.discover(query,limit=3)
        assert matches,(query,matches)
        assert matches[0].name==expected,(query,[m.name for m in matches])


def test_schemas():
    agent=create_agent()
    for name in ["prompt_construct","text_generate","text_summarize","text_extract","text_classify","text_transform"]:
        capability=agent.capabilities.get(name)
        assert capability.input_schema.get("type")=="object",name
        assert capability.output_schema,name


def test_runtime():
    agent=create_agent()
    state=agent.run("calculate 25 + 15")
    assert isinstance(state,JobState)
    assert state.status=="completed"


def main():
    tests=[
        ("registration",test_registration),
        ("prompt construction",test_prompt),
        ("text generation",test_generation),
        ("summarization",test_summary),
        ("information extraction",test_extract),
        ("classification",test_classify),
        ("text transformation",test_transform),
        ("capability discovery",test_discovery),
        ("capability schemas",test_schemas),
        ("core runtime regression",test_runtime),
    ]
    passed=sum(check(n,f) for n,f in tests)
    print(f"CP-17 GEN-AI TESTS: {passed}/{len(tests)} PASSED")
    if passed!=len(tests):
        raise SystemExit(1)


if __name__=="__main__":
    main()
