import logging
from django.db.models.signals import post_save
from django.dispatch import receiver

logger = logging.getLogger(__name__)


@receiver(post_save, sender='competency.CompetencyTestSession')
def update_skills_after_test(sender, instance, **kwargs):
    """After a test is completed, merge demonstrated skill_tags into the user's profile."""
    if not instance.completed:
        return

    try:
        profile = instance.user.userprofile
    except Exception:
        return

    # Collect skill_tags from all answers in this session
    from competency.models import Answer
    answers = Answer.objects.filter(session=instance)
    new_skills = set()
    for answer in answers:
        if answer.skill_tags:
            new_skills.update(answer.skill_tags)

    if not new_skills:
        return

    # Merge into existing extracted_skills
    existing = set(profile.extracted_skills or [])
    merged = list(existing | new_skills)

    if len(merged) != len(existing):
        profile.extracted_skills = merged
        profile.save(update_fields=['extracted_skills'])
        logger.info("Updated skills for %s: +%d new skills", instance.user.username, len(new_skills - existing))
