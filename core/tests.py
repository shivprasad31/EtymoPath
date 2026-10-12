from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from .models import (
    AssessmentAttempt,
    LearningLevel,
    Lesson,
    RevisionRecord,
    Root,
    RootWordLink,
    UserLessonProgress,
    Word,
)

User = get_user_model()


class EtymoPathWorkflowTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        call_command("seed_etymopath", verbosity=0)
        cls.lesson = Lesson.objects.get(slug="scrib-script-foundations")
        cls.user = User.objects.create_user(username="learner", email="learner@example.test", password="A-strong-test-password-28")
        cls.other_user = User.objects.create_user(username="other", email="other@example.test", password="A-strong-test-password-29")

    def test_public_homepage_and_explorer_render(self):
        self.assertEqual(self.client.get(reverse("core:home")).status_code, 200)
        response = self.client.get(reverse("core:explore"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "scrib / script")
        self.assertContains(response, "inscription")

    def test_seed_command_is_idempotent(self):
        before = (Root.objects.count(), Word.objects.count(), Lesson.objects.count())
        call_command("seed_etymopath", verbosity=0)
        after = (Root.objects.count(), Word.objects.count(), Lesson.objects.count())
        self.assertEqual(after, before)

    def test_registration_and_login(self):
        response = self.client.post(reverse("core:register"), {
            "username": "newlearner", "email": "new@example.test",
            "password1": "A-new-strong-password-2046", "password2": "A-new-strong-password-2046",
        })
        self.assertRedirects(response, reverse("core:dashboard"))
        self.assertTrue(User.objects.filter(username="newlearner").exists())
        self.client.post(reverse("logout"))
        self.assertNotIn("_auth_user_id", self.client.session)
        login_response = self.client.post(reverse("login"), {"username": "newlearner", "password": "A-new-strong-password-2046"})
        self.assertRedirects(login_response, reverse("core:dashboard"))

    def test_registration_rejects_invalid_password_and_duplicate_email(self):
        response = self.client.post(reverse("core:register"), {
            "username": "shortpw", "email": "short@example.test", "password1": "short", "password2": "short",
        })
        self.assertEqual(response.status_code, 200)
        self.assertFalse(User.objects.filter(username="shortpw").exists())
        duplicate = self.client.post(reverse("core:register"), {
            "username": "another", "email": "LEARNER@example.test",
            "password1": "A-new-strong-password-2046", "password2": "A-new-strong-password-2046",
        })
        self.assertEqual(duplicate.status_code, 200)
        self.assertFalse(User.objects.filter(username="another").exists())

    def test_private_pages_require_login(self):
        response = self.client.get(reverse("core:dashboard"))
        self.assertRedirects(response, f"{reverse('login')}?next={reverse('core:dashboard')}")
        self.assertRedirects(self.client.get(reverse("core:lesson", args=[self.lesson.slug])), f"{reverse('login')}?next={reverse('core:lesson', args=[self.lesson.slug])}")

    def test_learning_and_account_pages_render_for_the_right_audience(self):
        self.assertEqual(self.client.get(reverse("core:journey")).status_code, 200)
        self.assertEqual(self.client.get(reverse("password_reset")).status_code, 200)
        self.client.force_login(self.user)
        for url in (
            reverse("core:dashboard"),
            reverse("core:lesson", args=[self.lesson.slug]),
            reverse("core:quiz", args=[self.lesson.slug]),
            reverse("core:revision"),
            reverse("core:progress"),
            reverse("core:profile"),
        ):
            with self.subTest(url=url):
                self.assertEqual(self.client.get(url).status_code, 200)

    def test_database_search_handles_partial_casefold_and_empty_query(self):
        response = self.client.get(reverse("core:explore-search"), {"q": "SCRIPT"})
        self.assertEqual(response.status_code, 200)
        labels = [item["label"] for item in response.json()["results"]]
        self.assertIn("scrib / script", labels)
        self.assertIn("manuscript", labels)
        self.assertEqual(self.client.get(reverse("core:explore-search"), {"q": ""}).json(), {"results": []})
        self.assertEqual(self.client.get(reverse("core:explore-search"), {"q": "no-such-word"}).json(), {"results": []})

    def test_root_and_word_relationships_are_saved(self):
        root = Root.objects.get(slug="scrib-script")
        link = RootWordLink.objects.select_related("word").get(root=root, word__slug="manuscript")
        self.assertEqual(link.relationship_type, RootWordLink.RelationType.PARTICIPLE)
        self.assertEqual(link.morpheme_type, RootWordLink.MorphemeType.COMPONENT)
        self.assertTrue(link.word.outgoing_relationships.exists())

    def test_lesson_completion_is_persisted_and_idempotent(self):
        self.client.force_login(self.user)
        url = reverse("core:lesson-complete", args=[self.lesson.slug])
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(self.client.post(url).status_code, 302)
        self.assertEqual(UserLessonProgress.objects.filter(user=self.user, lesson=self.lesson).count(), 1)
        self.assertEqual(RevisionRecord.objects.filter(user=self.user).count(), self.lesson.words.count())

    def test_assessment_score_and_attempt_answers_are_computed_and_persisted(self):
        self.client.force_login(self.user)
        answers = {}
        questions = list(self.lesson.questions.prefetch_related("choices"))
        for question in questions:
            correct = question.choices.get(is_correct=True)
            answers[f"question_{question.pk}"] = str(correct.pk)
        response = self.client.post(reverse("core:quiz", args=[self.lesson.slug]), answers)
        attempt = AssessmentAttempt.objects.get(user=self.user, lesson=self.lesson)
        self.assertRedirects(response, reverse("core:attempt", args=[attempt.pk]))
        self.assertEqual(attempt.correct_answers, len(questions))
        self.assertEqual(attempt.percentage, 100)
        self.assertEqual(attempt.answers.count(), len(questions))

    def test_unanswered_assessment_is_incorrect_and_creates_revision_items(self):
        self.client.force_login(self.user)
        self.client.post(reverse("core:quiz", args=[self.lesson.slug]), {})
        attempt = AssessmentAttempt.objects.get(user=self.user)
        self.assertEqual(attempt.correct_answers, 0)
        self.assertEqual(attempt.answers.filter(selected_choice__isnull=True, is_correct=False).count(), attempt.question_count)
        self.assertEqual(RevisionRecord.objects.filter(user=self.user).count(), self.lesson.questions.count())

    def test_attempts_and_revision_records_are_private_to_the_owner(self):
        attempt = AssessmentAttempt.objects.create(user=self.user, lesson=self.lesson, score=0, question_count=3)
        word = Word.objects.get(slug="describe")
        record = RevisionRecord.objects.create(user=self.user, word=word)
        self.client.force_login(self.other_user)
        self.assertEqual(self.client.get(reverse("core:attempt", args=[attempt.pk])).status_code, 404)
        self.assertEqual(self.client.post(reverse("core:review-word", args=[record.pk]), {"result": "remembered"}).status_code, 404)
        self.assertFalse(RevisionRecord.objects.filter(user=self.other_user, word=word).exists())

    def test_review_schedule_updates_again_or_remembered(self):
        record = RevisionRecord.objects.create(user=self.user, word=Word.objects.get(slug="describe"), due_date=timezone.localdate())
        self.client.force_login(self.user)
        url = reverse("core:review-word", args=[record.pk])
        self.client.post(url, {"result": RevisionRecord.Result.REMEMBERED})
        record.refresh_from_db()
        self.assertEqual(record.interval_days, 2)
        self.assertEqual(record.due_date, timezone.localdate() + timedelta(days=2))
        self.client.post(url, {"result": RevisionRecord.Result.NEEDS_PRACTICE})
        record.refresh_from_db()
        self.assertEqual(record.interval_days, 1)
        self.assertEqual(record.due_date, timezone.localdate() + timedelta(days=1))
        self.assertEqual(record.review_count, 2)

    def test_dashboard_and_progress_are_user_specific(self):
        UserLessonProgress.objects.create(user=self.user, lesson=self.lesson)
        self.client.force_login(self.other_user)
        dashboard = self.client.get(reverse("core:dashboard"))
        self.assertEqual(dashboard.status_code, 200)
        self.assertEqual(dashboard.context["completed_count"], 0)
        self.assertEqual(dashboard.context["words_learned"], 0)
        progress = self.client.get(reverse("core:progress"))
        self.assertEqual(list(progress.context["completed"]), [])

    def test_levels_are_ordered(self):
        self.assertEqual(list(LearningLevel.objects.values_list("slug", flat=True)), ["beginner", "intermediate", "advanced"])

