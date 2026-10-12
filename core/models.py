from django.conf import settings
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class EditorialStatus(models.TextChoices):
    VERIFIED = "verified", "Verified"
    REVIEW = "review", "Needs editorial review"


class Root(models.Model):
    slug = models.SlugField(unique=True)
    display = models.CharField(max_length=100)
    language = models.CharField(max_length=60, default="Latin")
    origin_form = models.CharField(max_length=120)
    meaning = models.CharField(max_length=180)
    source_url = models.URLField(blank=True)
    editorial_status = models.CharField(max_length=12, choices=EditorialStatus.choices, default=EditorialStatus.REVIEW)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "display"]

    def __str__(self):
        return self.display


class Word(models.Model):
    slug = models.SlugField(unique=True)
    spelling = models.CharField(max_length=100, unique=True)
    part_of_speech = models.CharField(max_length=80, blank=True)
    definition = models.TextField()
    pronunciation = models.CharField(max_length=120, blank=True)
    syllables = models.CharField(max_length=120, blank=True)
    etymology = models.TextField(blank=True)
    example = models.TextField(blank=True)
    dictionary_url = models.URLField(blank=True)
    etymology_url = models.URLField(blank=True)
    editorial_status = models.CharField(max_length=12, choices=EditorialStatus.choices, default=EditorialStatus.REVIEW)
    roots = models.ManyToManyField(Root, through="RootWordLink", related_name="words")

    class Meta:
        ordering = ["spelling"]
        indexes = [models.Index(fields=["spelling"])]

    def __str__(self):
        return self.spelling


class RootWordLink(models.Model):
    class RelationType(models.TextChoices):
        DERIVED = "derived", "Derived from root"
        PARTICIPLE = "participle", "Participle-based form"
        ROOT_RELATED = "root_related", "Root-related borrowing"
        SHARED = "shared", "Shares historical root"

    class MorphemeType(models.TextChoices):
        PREFIX = "prefix", "Prefix"
        SUFFIX = "suffix", "Suffix"
        COMPONENT = "component", "Compound element"
        ROOT_FORM = "root_form", "Root form"

    root = models.ForeignKey(Root, on_delete=models.CASCADE, related_name="word_links")
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="root_links")
    relationship_type = models.CharField(max_length=20, choices=RelationType.choices)
    morpheme_type = models.CharField(max_length=12, choices=MorphemeType.choices, blank=True)
    morpheme = models.CharField(max_length=50, blank=True)
    morpheme_meaning = models.CharField(max_length=100, blank=True)
    branch_label = models.CharField(max_length=140, blank=True)

    class Meta:
        ordering = ["branch_label", "word__spelling"]
        constraints = [models.UniqueConstraint(fields=["root", "word"], name="unique_root_word_link")]

    def __str__(self):
        return f"{self.word} ↔ {self.root}"


class WordRelationship(models.Model):
    class RelationType(models.TextChoices):
        DERIVED_FROM = "derived_from", "Derived from"
        SHARES_ROOT = "shares_root", "Shares historical root with"
        PREFIX = "prefix", "Contains prefix"
        SUFFIX = "suffix", "Contains suffix"
        RELATED = "related", "Related vocabulary"

    source_word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="outgoing_relationships")
    target_word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="incoming_relationships")
    relationship_type = models.CharField(max_length=20, choices=RelationType.choices)
    label = models.CharField(max_length=140, blank=True)
    source_url = models.URLField(blank=True)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["source_word", "target_word", "relationship_type"], name="unique_word_relationship")]

    def clean(self):
        if self.source_word_id and self.source_word_id == self.target_word_id:
            raise ValidationError("A word cannot be related to itself.")


class LearningLevel(models.Model):
    slug = models.SlugField(unique=True)
    name = models.CharField(max_length=40, unique=True)
    description = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(unique=True)

    class Meta:
        ordering = ["order"]

    def __str__(self):
        return self.name


class LearningModule(models.Model):
    level = models.ForeignKey(LearningLevel, on_delete=models.CASCADE, related_name="modules")
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150)
    summary = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["level__order", "order"]
        constraints = [models.UniqueConstraint(fields=["level", "order"], name="unique_module_order_per_level")]

    def __str__(self):
        return self.title


class Lesson(models.Model):
    module = models.ForeignKey(LearningModule, on_delete=models.CASCADE, related_name="lessons")
    slug = models.SlugField(unique=True)
    title = models.CharField(max_length=150)
    introduction = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)
    words = models.ManyToManyField(Word, through="LessonWord", related_name="lessons")

    class Meta:
        ordering = ["module__level__order", "module__order", "order"]
        constraints = [models.UniqueConstraint(fields=["module", "order"], name="unique_lesson_order_per_module")]

    def __str__(self):
        return self.title


class LessonWord(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="lesson_words")
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="lesson_entries")
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order"]
        constraints = [
            models.UniqueConstraint(fields=["lesson", "word"], name="unique_word_per_lesson"),
            models.UniqueConstraint(fields=["lesson", "order"], name="unique_word_order_per_lesson"),
        ]


class QuizQuestion(models.Model):
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="questions")
    word = models.ForeignKey(Word, on_delete=models.SET_NULL, related_name="quiz_questions", null=True, blank=True)
    prompt = models.TextField()
    explanation = models.TextField(blank=True)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]
        constraints = [models.UniqueConstraint(fields=["lesson", "order"], name="unique_question_order_per_lesson")]

    def clean(self):
        if self.pk:
            choice_count = self.choices.count()
            if choice_count and (choice_count < 2 or self.choices.filter(is_correct=True).count() != 1):
                raise ValidationError("Each assessment question must have at least two choices and exactly one correct answer.")


class AnswerChoice(models.Model):
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="choices")
    text = models.CharField(max_length=240)
    is_correct = models.BooleanField(default=False)
    order = models.PositiveSmallIntegerField(default=0)

    class Meta:
        ordering = ["order", "pk"]
        constraints = [models.UniqueConstraint(fields=["question", "order"], name="unique_choice_order_per_question")]

    def __str__(self):
        return self.text


class UserLessonProgress(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="lesson_progress")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="user_progress")
    completed_at = models.DateTimeField(default=timezone.now)

    class Meta:
        ordering = ["-completed_at"]
        constraints = [models.UniqueConstraint(fields=["user", "lesson"], name="unique_user_lesson_progress")]


class AssessmentAttempt(models.Model):
    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="assessment_attempts")
    lesson = models.ForeignKey(Lesson, on_delete=models.CASCADE, related_name="assessment_attempts")
    score = models.PositiveSmallIntegerField()
    question_count = models.PositiveSmallIntegerField()
    submitted_at = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        ordering = ["-submitted_at"]

    @property
    def percentage(self):
        return round(self.score / self.question_count * 100) if self.question_count else 0

    @property
    def correct_answers(self):
        return self.score


class AssessmentAnswer(models.Model):
    attempt = models.ForeignKey(AssessmentAttempt, on_delete=models.CASCADE, related_name="answers")
    question = models.ForeignKey(QuizQuestion, on_delete=models.CASCADE, related_name="submitted_answers")
    selected_choice = models.ForeignKey(AnswerChoice, on_delete=models.SET_NULL, null=True, blank=True, related_name="submissions")
    is_correct = models.BooleanField(default=False)

    class Meta:
        constraints = [models.UniqueConstraint(fields=["attempt", "question"], name="unique_answer_per_attempt_question")]


class RevisionRecord(models.Model):
    class Result(models.TextChoices):
        NEEDS_PRACTICE = "practice", "Needs practice"
        REMEMBERED = "remembered", "Remembered"

    user = models.ForeignKey(settings.AUTH_USER_MODEL, on_delete=models.CASCADE, related_name="revision_records")
    word = models.ForeignKey(Word, on_delete=models.CASCADE, related_name="revision_records")
    due_date = models.DateField(default=timezone.localdate, db_index=True)
    interval_days = models.PositiveSmallIntegerField(default=1)
    review_count = models.PositiveIntegerField(default=0)
    last_result = models.CharField(max_length=12, choices=Result.choices, blank=True)
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        ordering = ["due_date", "word__spelling"]
        constraints = [models.UniqueConstraint(fields=["user", "word"], name="unique_user_revision_word")]
        indexes = [models.Index(fields=["user", "due_date"])]

    @property
    def is_due(self):
        return self.due_date <= timezone.localdate()
