from django.contrib import admin
from django.core.exceptions import ValidationError
from django.forms.models import BaseInlineFormSet

from .models import (
    AnswerChoice,
    AssessmentAnswer,
    AssessmentAttempt,
    LearningLevel,
    LearningModule,
    Lesson,
    LessonWord,
    QuizQuestion,
    RevisionRecord,
    Root,
    RootWordLink,
    UserLessonProgress,
    Word,
    WordRelationship,
)


class RootWordInline(admin.TabularInline):
    model = RootWordLink
    extra = 0
    autocomplete_fields = ["word"]


class ExactlyOneCorrectChoiceFormSet(BaseInlineFormSet):
    def clean(self):
        super().clean()
        if any(self.errors):
            return
        active_choices = [
            form.cleaned_data for form in self.forms
            if form.cleaned_data and form.cleaned_data.get("text") and not form.cleaned_data.get("DELETE", False)
        ]
        if active_choices and (len(active_choices) < 2 or sum(bool(choice.get("is_correct")) for choice in active_choices) != 1):
            raise ValidationError("Each assessment question must have exactly one correct choice.")


class ChoiceInline(admin.TabularInline):
    model = AnswerChoice
    formset = ExactlyOneCorrectChoiceFormSet
    extra = 3


class QuestionInline(admin.StackedInline):
    model = QuizQuestion
    extra = 0
    show_change_link = True
    autocomplete_fields = ["word"]


class LessonWordInline(admin.TabularInline):
    model = LessonWord
    extra = 0
    autocomplete_fields = ["word"]


@admin.register(Root)
class RootAdmin(admin.ModelAdmin):
    list_display = ["display", "language", "meaning", "editorial_status", "order"]
    list_filter = ["language", "editorial_status"]
    search_fields = ["display", "origin_form", "meaning"]
    prepopulated_fields = {"slug": ["display"]}
    inlines = [RootWordInline]


@admin.register(Word)
class WordAdmin(admin.ModelAdmin):
    list_display = ["spelling", "part_of_speech", "editorial_status"]
    list_filter = ["editorial_status", "part_of_speech"]
    search_fields = ["spelling", "definition", "etymology"]
    prepopulated_fields = {"slug": ["spelling"]}


@admin.register(WordRelationship)
class WordRelationshipAdmin(admin.ModelAdmin):
    list_display = ["source_word", "relationship_type", "target_word", "label"]
    list_filter = ["relationship_type"]
    search_fields = ["source_word__spelling", "target_word__spelling", "label"]
    autocomplete_fields = ["source_word", "target_word"]


@admin.register(LearningLevel)
class LearningLevelAdmin(admin.ModelAdmin):
    list_display = ["name", "order"]
    prepopulated_fields = {"slug": ["name"]}


@admin.register(LearningModule)
class LearningModuleAdmin(admin.ModelAdmin):
    list_display = ["title", "level", "order"]
    list_filter = ["level"]
    prepopulated_fields = {"slug": ["title"]}


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ["title", "module", "order"]
    list_filter = ["module__level", "module"]
    search_fields = ["title", "slug"]
    prepopulated_fields = {"slug": ["title"]}
    inlines = [LessonWordInline, QuestionInline]


@admin.register(QuizQuestion)
class QuizQuestionAdmin(admin.ModelAdmin):
    list_display = ["prompt", "lesson", "word", "order"]
    list_filter = ["lesson__module__level"]
    search_fields = ["prompt", "lesson__title", "word__spelling"]
    autocomplete_fields = ["lesson", "word"]
    inlines = [ChoiceInline]


@admin.register(UserLessonProgress)
class UserLessonProgressAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "completed_at"]
    list_filter = ["lesson__module__level", "completed_at"]
    search_fields = ["user__username", "lesson__title"]


@admin.register(AssessmentAttempt)
class AssessmentAttemptAdmin(admin.ModelAdmin):
    list_display = ["user", "lesson", "score", "question_count", "submitted_at"]
    list_filter = ["lesson__module__level", "submitted_at"]
    search_fields = ["user__username", "lesson__title"]
    readonly_fields = ["user", "lesson", "score", "question_count", "submitted_at"]


@admin.register(AssessmentAnswer)
class AssessmentAnswerAdmin(admin.ModelAdmin):
    list_display = ["attempt", "question", "selected_choice", "is_correct"]
    list_filter = ["is_correct"]


@admin.register(RevisionRecord)
class RevisionRecordAdmin(admin.ModelAdmin):
    list_display = ["user", "word", "due_date", "interval_days", "review_count", "last_result"]
    list_filter = ["last_result", "due_date"]
    search_fields = ["user__username", "word__spelling"]
