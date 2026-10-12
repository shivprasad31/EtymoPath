from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.home, name="home"),
    path("explore/", views.explore, name="explore"),
    path("explore/search/", views.explore_search, name="explore-search"),
    path("register/", views.register, name="register"),
    path("dashboard/", views.dashboard, name="dashboard"),
    path("journey/", views.journey, name="journey"),
    path("lesson/<slug:slug>/", views.lesson_detail, name="lesson"),
    path("lesson/<slug:slug>/complete/", views.lesson_complete, name="lesson-complete"),
    path("lesson/<slug:slug>/quiz/", views.quiz, name="quiz"),
    path("attempt/<int:attempt_id>/", views.attempt_detail, name="attempt"),
    path("revision/", views.revision, name="revision"),
    path("revision/<int:record_id>/review/", views.review_word, name="review-word"),
    path("progress/", views.progress, name="progress"),
    path("profile/", views.profile, name="profile"),
]
