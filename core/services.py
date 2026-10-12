from datetime import timedelta

from django.db import transaction
from django.utils import timezone

from .models import (
    AssessmentAnswer,
    AssessmentAttempt,
    RevisionRecord,
    UserLessonProgress,
)


@transaction.atomic
def complete_lesson(user, lesson):
    progress, created = UserLessonProgress.objects.get_or_create(user=user, lesson=lesson)
    for lesson_word in lesson.lesson_words.select_related("word"):
        RevisionRecord.objects.get_or_create(user=user, word=lesson_word.word)
    return progress, created


@transaction.atomic
def submit_assessment(user, lesson, posted_answers):
    questions = list(lesson.questions.prefetch_related("choices").select_related("word"))
    evaluated = []
    correct_count = 0
    for question in questions:
        choice_id = posted_answers.get(f"question_{question.pk}")
        choice = next((item for item in question.choices.all() if str(item.pk) == str(choice_id)), None)
        is_correct = bool(choice and choice.is_correct)
        correct_count += int(is_correct)
        evaluated.append((question, choice, is_correct))

    attempt = AssessmentAttempt.objects.create(
        user=user,
        lesson=lesson,
        score=correct_count,
        question_count=len(questions),
    )
    for question, choice, is_correct in evaluated:
        AssessmentAnswer.objects.create(
            attempt=attempt,
            question=question,
            selected_choice=choice,
            is_correct=is_correct,
        )
        if question.word_id and not is_correct:
            RevisionRecord.objects.update_or_create(
                user=user,
                word=question.word,
                defaults={"due_date": timezone.localdate(), "interval_days": 1, "last_result": RevisionRecord.Result.NEEDS_PRACTICE},
            )
    return attempt


@transaction.atomic
def record_word_review(record, result):
    if result == RevisionRecord.Result.NEEDS_PRACTICE:
        interval = 1
    elif result == RevisionRecord.Result.REMEMBERED:
        interval = min(max(record.interval_days, 1) * 2, 30)
    else:
        raise ValueError("Unknown revision result.")
    record.interval_days = interval
    record.review_count += 1
    record.last_result = result
    record.last_reviewed_at = timezone.now()
    record.due_date = timezone.localdate() + timedelta(days=interval)
    record.save(update_fields=["interval_days", "review_count", "last_result", "last_reviewed_at", "due_date"])
    return record
