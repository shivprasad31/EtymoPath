from django.contrib import messages
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.db.models import Q
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_POST

from .forms import ProfileForm, RegistrationForm
from .models import (
    AssessmentAttempt,
    LearningLevel,
    Lesson,
    RevisionRecord,
    Root,
    UserLessonProgress,
    Word,
)
from .services import complete_lesson, record_word_review, submit_assessment


def home(request):
    return render(request, "core/home.html")


def _root_payload(root):
    groups = {}
    for link in root.word_links.filter(word__editorial_status="verified").select_related("word"):
        item = link.word
        groups.setdefault(link.branch_label or "Related forms", []).append({
            "id": item.slug,
            "word": item.spelling,
            "pronunciation": item.pronunciation or None,
            "syllables": item.syllables or None,
            "part_of_speech": item.part_of_speech,
            "meaning": item.definition,
            "etymology": item.etymology,
            "relationship": link.get_relationship_type_display(),
            "example": item.example,
            "dictionary_url": item.dictionary_url,
            "etymology_url": item.etymology_url,
        })
    return {
        "id": root.slug,
        "label": root.display,
        "origin": f"{root.language} {root.origin_form}",
        "gloss": root.meaning,
        "source": root.source_url,
        "groups": [
            {"id": f"branch-{index}", "label": label, "words": words}
            for index, (label, words) in enumerate(groups.items())
        ],
    }


def explore(request):
    roots = Root.objects.filter(editorial_status="verified").prefetch_related("word_links__word").order_by("order")
    root_payloads = [_root_payload(root) for root in roots]
    selected_root = next((root for root in root_payloads if root["id"] == request.GET.get("root")), root_payloads[0] if root_payloads else None)
    selected_word = request.GET.get("word", "")
    if selected_root and selected_word not in {word["id"] for group in selected_root["groups"] for word in group["words"]}:
        selected_word = ""
    selected_word_payload = next((word for group in selected_root["groups"] for word in group["words"] if word["id"] == selected_word), None) if selected_root else None
    term = request.GET.get("q", "").strip()[:100]
    search_results = []
    if term:
        for root in Root.objects.filter(editorial_status="verified").filter(
            Q(display__icontains=term) | Q(origin_form__icontains=term) | Q(meaning__icontains=term)
        ).order_by("order")[:8]:
            search_results.append({"kind": "root", "label": root.display, "meta": f"Root · {root.meaning}", "root_id": root.slug})
        for word in Word.objects.filter(editorial_status="verified").filter(
            Q(spelling__icontains=term) | Q(definition__icontains=term) | Q(etymology__icontains=term)
        ).prefetch_related("root_links__root").distinct().order_by("spelling")[:20]:
            link = next(iter(word.root_links.all()), None)
            search_results.append({"kind": "word", "label": word.spelling, "meta": f"{link.root.display} · {word.part_of_speech}" if link else word.part_of_speech, "root_id": link.root.slug if link else "", "word_id": word.slug})
    return render(request, "core/explore.html", {
        "roots": root_payloads,
        "selected_root": selected_root,
        "selected_root_id": selected_root["id"] if selected_root else "",
        "selected_word_id": selected_word,
        "selected_word": selected_word_payload,
        "search_query": term,
        "search_results": search_results,
    })


def explore_search(request):
    term = request.GET.get("q", "").strip()[:100]
    if not term:
        return JsonResponse({"results": []})
    roots = Root.objects.filter(editorial_status="verified").filter(
        Q(display__icontains=term) | Q(origin_form__icontains=term) | Q(meaning__icontains=term)
    ).order_by("order")[:8]
    words = Word.objects.filter(editorial_status="verified").filter(
        Q(spelling__icontains=term) | Q(definition__icontains=term) | Q(etymology__icontains=term)
    ).prefetch_related("root_links__root").distinct().order_by("spelling")[:20]
    results = [
        {"kind": "root", "id": root.slug, "label": root.display, "meta": f"Root · {root.meaning}"}
        for root in roots
    ]
    for word in words:
        link = next(iter(word.root_links.all()), None)
        results.append({
            "kind": "word", "id": word.slug, "label": word.spelling,
            "root_id": link.root.slug if link else "",
            "meta": f"{link.root.display} · {word.part_of_speech}" if link else word.part_of_speech,
        })
    return JsonResponse({"results": results})


def register(request):
    if request.user.is_authenticated:
        return redirect("core:dashboard")
    form = RegistrationForm(request.POST or None)
    if request.method == "POST" and form.is_valid():
        user = form.save()
        login(request, user)
        messages.success(request, "Your account is ready. Choose a lesson to begin.")
        return redirect("core:dashboard")
    return render(request, "core/register.html", {"form": form})


@login_required
def dashboard(request):
    today = timezone.localdate()
    completed_ids = UserLessonProgress.objects.filter(user=request.user).values_list("lesson_id", flat=True)
    total_lessons = Lesson.objects.count()
    completed_count = UserLessonProgress.objects.filter(user=request.user).count()
    latest_attempt = AssessmentAttempt.objects.filter(user=request.user).select_related("lesson").first()
    due_count = RevisionRecord.objects.filter(user=request.user, due_date__lte=today).count()
    words_learned = RevisionRecord.objects.filter(user=request.user).count()
    root_count = Root.objects.filter(words__revision_records__user=request.user).distinct().count()
    current_level = LearningLevel.objects.filter(
        modules__lessons__user_progress__user=request.user
    ).order_by("-order").first()
    next_lesson = Lesson.objects.exclude(pk__in=completed_ids).select_related("module__level").first()
    recent_progress = UserLessonProgress.objects.filter(user=request.user).select_related("lesson__module__level")[:4]
    return render(request, "core/dashboard.html", {
        "total_lessons": total_lessons,
        "completed_count": completed_count,
        "completion_percent": round(completed_count / total_lessons * 100) if total_lessons else 0,
        "latest_attempt": latest_attempt,
        "due_count": due_count,
        "words_learned": words_learned,
        "root_count": root_count,
        "current_level": current_level,
        "next_lesson": next_lesson,
        "recent_progress": recent_progress,
    })


def journey(request):
    levels = LearningLevel.objects.prefetch_related("modules__lessons").order_by("order")
    completed_ids = set()
    if request.user.is_authenticated:
        completed_ids = set(UserLessonProgress.objects.filter(user=request.user).values_list("lesson_id", flat=True))
    return render(request, "core/journey.html", {"levels": levels, "completed_ids": completed_ids})


@login_required
def lesson_detail(request, slug):
    lesson = get_object_or_404(
        Lesson.objects.select_related("module__level").prefetch_related("lesson_words__word__root_links__root"),
        slug=slug,
    )
    progress_record = UserLessonProgress.objects.filter(user=request.user, lesson=lesson).first()
    completed = progress_record is not None
    siblings = list(Lesson.objects.select_related("module__level").order_by("module__level__order", "module__order", "order"))
    index = siblings.index(lesson)
    return render(request, "core/lesson.html", {
        "lesson": lesson,
        "completed": completed,
        "completed_at": progress_record.completed_at if progress_record else None,
        "previous_lesson": siblings[index - 1] if index > 0 else None,
        "next_lesson": siblings[index + 1] if index + 1 < len(siblings) else None,
    })


@login_required
@require_POST
def lesson_complete(request, slug):
    lesson = get_object_or_404(Lesson, slug=slug)
    _progress, created = complete_lesson(request.user, lesson)
    messages.success(request, "Lesson marked complete. Words from this lesson are now in your revision list." if created else "This lesson was already complete.")
    return redirect("core:lesson", slug=slug)


@login_required
def quiz(request, slug):
    lesson = get_object_or_404(Lesson.objects.select_related("module__level").prefetch_related("questions__choices__question"), slug=slug)
    questions = lesson.questions.prefetch_related("choices").select_related("word")
    if not questions.exists():
        messages.info(request, "This lesson does not have an assessment yet.")
        return redirect("core:lesson", slug=slug)
    if any(question.choices.count() < 2 or question.choices.filter(is_correct=True).count() != 1 for question in questions):
        messages.error(request, "This assessment is not ready yet. Please ask a content editor to finish its answer choices.")
        return redirect("core:lesson", slug=slug)
    if request.method == "POST":
        attempt = submit_assessment(request.user, lesson, request.POST)
        messages.success(request, "Your assessment attempt has been saved.")
        return redirect("core:attempt", attempt_id=attempt.pk)
    return render(request, "core/quiz.html", {"lesson": lesson, "questions": questions})


@login_required
def attempt_detail(request, attempt_id):
    attempt = get_object_or_404(
        AssessmentAttempt.objects.filter(user=request.user).select_related("lesson__module__level").prefetch_related("answers__question__choices", "answers__selected_choice"),
        pk=attempt_id,
    )
    answers = attempt.answers.all().order_by("question__order")
    return render(request, "core/attempt.html", {"attempt": attempt, "answers": answers})


@login_required
def revision(request):
    records = RevisionRecord.objects.filter(user=request.user).select_related("word").prefetch_related("word__root_links__root")
    due_records = records.filter(due_date__lte=timezone.localdate())
    return render(request, "core/revision.html", {"due_records": due_records, "upcoming_records": records.exclude(pk__in=due_records.values("pk"))[:20]})


@login_required
@require_POST
def review_word(request, record_id):
    record = get_object_or_404(RevisionRecord, user=request.user, pk=record_id)
    result = request.POST.get("result")
    if result not in RevisionRecord.Result.values:
        messages.error(request, "Choose one of the review options to continue.")
    else:
        record_word_review(record, result)
        label = "1 day" if result == RevisionRecord.Result.NEEDS_PRACTICE else f"{record.interval_days} days"
        messages.success(request, f"Review saved. This word is due again in {label}.")
    return redirect("core:revision")


@login_required
def progress(request):
    completed = UserLessonProgress.objects.filter(user=request.user).select_related("lesson__module__level")
    attempts = AssessmentAttempt.objects.filter(user=request.user).select_related("lesson__module__level")[:30]
    records = RevisionRecord.objects.filter(user=request.user).select_related("word").prefetch_related("word__root_links__root")
    return render(request, "core/progress.html", {"completed": completed, "attempts": attempts, "records": records})


@login_required
def profile(request):
    form = ProfileForm(request.POST or None, instance=request.user)
    if request.method == "POST" and form.is_valid():
        form.save()
        messages.success(request, "Account details updated.")
        return redirect("core:profile")
    return render(request, "core/profile.html", {"form": form})
