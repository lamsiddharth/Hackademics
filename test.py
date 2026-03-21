import os
import sys
import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
django.setup()

from competency.utils import generate_questions_for_job, save_generated_questions

try:
    print("Generating...")
    raw_output = generate_questions_for_job("data-scientist")
    print(f"Raw Output: {raw_output}")
    print("Saving...")
    saved_count = save_generated_questions(raw_output, "data-scientist")
    print(f"Saved: {saved_count}")
except Exception as e:
    import traceback
    traceback.print_exc()
