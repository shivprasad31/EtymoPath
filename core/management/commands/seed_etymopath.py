import json
from itertools import combinations
from pathlib import Path

from django.core.management.base import BaseCommand
from django.db import transaction

from core.models import (
    AnswerChoice,
    LearningLevel,
    LearningModule,
    Lesson,
    LessonWord,
    QuizQuestion,
    Root,
    RootWordLink,
    Word,
    WordRelationship,
)


DATA_DIR = Path(__file__).resolve().parents[2] / "data"


class Command(BaseCommand):
    help = "Load the curated word families and learning path. Safe to run repeatedly."

    @transaction.atomic
    def handle(self, *args, **options):
        roots_data = json.loads((DATA_DIR / "roots.json").read_text(encoding="utf-8"))
        lessons_data = json.loads((DATA_DIR / "learning_path.json").read_text(encoding="utf-8"))
        words = {}

        for root_index, root_data in enumerate(roots_data, start=1):
            origin_form, _, _meaning = root_data["origin"].partition(" (")
            root, _ = Root.objects.update_or_create(
                slug=root_data["id"],
                defaults={
                    "display": root_data["label"],
                    "language": "Latin",
                    "origin_form": origin_form,
                    "meaning": root_data["gloss"],
                    "source_url": root_data["source"],
                    "editorial_status": "verified",
                    "order": root_index,
                },
            )
            for group in root_data["groups"]:
                morpheme, separator, meaning = group["label"].partition(" · ")
                for item in group["words"]:
                    word, _ = Word.objects.update_or_create(
                        slug=item["id"],
                        defaults={
                            "spelling": item["word"],
                            "part_of_speech": item["part_of_speech"],
                            "definition": item["meaning"],
                            "pronunciation": item.get("pronunciation") or "",
                            "syllables": item.get("syllables") or "",
                            "etymology": item["etymology"],
                            "example": item["example"],
                            "dictionary_url": item["dictionary_url"],
                            "etymology_url": item["etymology_url"],
                            "editorial_status": "verified",
                        },
                    )
                    words[word.slug] = word
                    relation_label = item["relationship"]
                    relation_type = "participle" if relation_label.startswith("Participle") else (
                        "root_related" if relation_label.startswith("Root-related") else "derived"
                    )
                    if morpheme.startswith("-"):
                        morpheme_type = "suffix"
                    elif morpheme == "manu":
                        morpheme_type = "component"
                    else:
                        morpheme_type = "prefix"
                    RootWordLink.objects.update_or_create(
                        root=root,
                        word=word,
                        defaults={
                            "relationship_type": relation_type,
                            "morpheme_type": morpheme_type,
                            "morpheme": morpheme,
                            "morpheme_meaning": meaning if separator else "",
                            "branch_label": group["label"],
                        },
                    )

            family_words = list(root.words.order_by("pk"))
            for left, right in combinations(family_words, 2):
                WordRelationship.objects.update_or_create(
                    source_word=left,
                    target_word=right,
                    relationship_type="shares_root",
                    defaults={"label": root.display, "source_url": root.source_url},
                )

        for level_data in lessons_data["levels"]:
            level, _ = LearningLevel.objects.update_or_create(
                slug=level_data["slug"],
                defaults={"name": level_data["name"], "description": level_data["description"], "order": level_data["order"]},
            )
            module_data = level_data["module"]
            module, _ = LearningModule.objects.update_or_create(
                slug=module_data["slug"],
                defaults={"level": level, "title": module_data["title"], "summary": module_data["summary"], "order": module_data["order"]},
            )
            lesson_data = module_data["lesson"]
            lesson, _ = Lesson.objects.update_or_create(
                slug=lesson_data["slug"],
                defaults={"module": module, "title": lesson_data["title"], "introduction": lesson_data["introduction"], "order": lesson_data["order"]},
            )
            for order, slug in enumerate(lesson_data["words"], start=1):
                LessonWord.objects.update_or_create(lesson=lesson, order=order, defaults={"word": words[slug]})

            for order, question_data in enumerate(lesson_data["questions"], start=1):
                question, _ = QuizQuestion.objects.update_or_create(
                    lesson=lesson,
                    order=order,
                    defaults={
                        "word": words.get(question_data.get("word")),
                        "prompt": question_data["prompt"],
                        "explanation": question_data["explanation"],
                    },
                )
                for choice_order, (text, is_correct) in enumerate(question_data["choices"], start=1):
                    AnswerChoice.objects.update_or_create(
                        question=question,
                        order=choice_order,
                        defaults={"text": text, "is_correct": is_correct},
                    )

        self.stdout.write(self.style.SUCCESS(
            f"Seeded {Root.objects.count()} roots, {Word.objects.count()} words, and {Lesson.objects.count()} lessons."
        ))
