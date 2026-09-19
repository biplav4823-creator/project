import re
import json

from .llm import ask_ollama
from .router import Router
from .executor import Executor
from .verifier import Verifier
from .explainer import Explainer
from tools.registry import ToolRegistry, Tool



class Agent:

    def __init__(self):
        self.tools = ToolRegistry()
        self.router = Router()
        self.executor = Executor()
        self.verifier = Verifier()
        self.explainer = Explainer()

    def register_tool(self, name, description, function):
        self.tools.register(Tool(name=name, description=description, function=function))

    def _find_tool(self, name):
        return self.tools.get(name)

    def _local_math(self, text):
        from tools.mathematics import calculate, derivative, integral, definite_integral, limit, solve_equation, factor, expand, simplify, numerical
        original = text.strip()
        s = original.lower().strip()
        if re.fullmatch(r'[0-9+\-*/().%\s^]+', s):
            try: return calculate(original)
            except Exception: pass
        m = re.search(r'(?:derivative|differentiate|differentiation)(?:\\s+of)?\\s+(.+)', s)
        if m:
            try: return derivative(re.sub(r'\\s+(with\\s+respect\\s+to|wrt)\\s+[a-z]\\s*$', '', m.group(1).strip()))
            except Exception: pass
        m = re.search(r'(?:integral|integrate|integration)(?:\\s+of)?\\s+(.+)', s)
        if m:
            expression=m.group(1).strip(); d=re.search(r'(.+?)\\s+from\\s+(.+?)\\s+to\\s+(.+)', expression)
            try: return definite_integral(d.group(1).strip(),'x',d.group(2).strip(),d.group(3).strip()) if d else integral(expression)
            except Exception: pass
        m = re.search(r'(?:limit)\\s+(?:of\\s+)?(.+?)\\s+(?:as|when)\\s+([a-zA-Z])\\s*(?:->|to)\\s*(.+)', s)
        if m:
            try: return limit(m.group(1).strip(),m.group(2).strip(),m.group(3).strip())
            except Exception: pass
        m = re.search(r'(?:solve|solution\\s+of|find\\s+the\\s+roots?)\\s+(.+)', s)
        if m and '=' in m.group(1):
            try: return solve_equation(m.group(1).strip(),'x')
            except Exception: pass
        for pattern, fn in [(r'(?:factor|factorize|factorise)(?:\\s+)?(?:the\\s+expression\\s+)?(.+)',factor),(r'(?:expand)(?:\\s+)?(?:the\\s+expression\\s+)?(.+)',expand),(r'(?:simplify)(?:\\s+)?(?:the\\s+expression\\s+)?(.+)',simplify),(r'(?:numerical value|approximate|approximation)(?:\\s+of)?\\s+(.+)',numerical)]:
            m=re.search(pattern,s)
            if m:
                try: return fn(m.group(1).strip())
                except Exception: pass
        return None

    def decide(self, user_input):
        tools=self.tools.list_tools()
        tool_text='\\n'.join(f'- {tool.name}: {tool.description}' for tool in tools)
        prompt=f'''You are JARVIS, a local AI assistant.\\n\\nAvailable tools:\\n{tool_text}\\n\\nUser request:\\n{user_input}\\n\\nReturn ONLY valid JSON with action, tool and arguments. Never invent tools. Use a registered tool when appropriate. Do not calculate mathematics yourself when a mathematical tool is available.'''
        result=ask_ollama(prompt)
        try: return json.loads(result)
        except json.JSONDecodeError:
            match=re.search(r'\\{.*\\}',result,re.DOTALL)
            if match:
                try: return json.loads(match.group(0))
                except Exception: pass
        return {'action':'answer','tool':None,'arguments':{}}

    def run(self, user_input):
        user_input=user_input.strip()
        if not user_input: return 'Please provide a request.'
        math_result=self._local_math(user_input)
        if math_result is not None: return str(math_result)
        decision=self.decide(user_input)
        route=self.router.route(decision)
        if route.action=='tool':
            try:
                result=self.executor.execute(self.tools,route.tool,route.arguments)
                verified=self.verifier.verify(result)
                return self.explainer.explain(verified['result'])
            except Exception as e: return f'Tool execution failed: {e}'
        return ask_ollama(user_input)

