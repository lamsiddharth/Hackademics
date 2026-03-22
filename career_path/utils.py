import google.generativeai as genai
from django.conf import settings

def generate_career_graph(user_profile):
    """
    Generates a career progression graph using the Gemini API.
    """
    genai.configure(api_key=settings.GEMINI_API_KEY)
    model = genai.GenerativeModel(settings.GEMINI_MODEL)

    prompt = f"""
    Based on the following user profile, generate a career progression graph.
    The user's skills are: {user_profile.skills}.
    The user's education is: {user_profile.education}.
    The user's experience is: {user_profile.experience}.

    The graph should have job roles as nodes and skills to be learned as edges.
    The output should be a JSON object representing the graph, with 'nodes' and 'edges' as keys.
    Nodes should have 'id' and 'label' attributes.
    Edges should have 'from', 'to', and 'label' attributes.
    The JSON should be clean and not enclosed in markdown backticks.
    """

    try:
        response = model.generate_content(prompt)
        text = response.text
        print(f"Gemini API response: {text}")
        # Attempt to clean up the response by extracting JSON from markdown
        if '```json' in text:
            text = text.split('```json')[1].split('```')[0]
        return text
    except Exception as e:
        print(f"An error occurred: {e}")
        return None
