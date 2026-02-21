"""
URL configuration for isports project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.2/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path
from app import views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls), # Django's default admin
    path('', views.index, name='index'),
    path('login/', views.login_view, name='login'),
    path('logout/', views.logout_view, name='logout'),
    path('register/', views.register_view, name='register'),
    path('admin-dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('user-dashboard/', views.user_dashboard, name='user_dashboard'),
    path('user-onboarding/', views.user_onboarding, name='user_onboarding'),
    path('events/', views.events_list, name='events_list'),
    path('profile/', views.profile_view, name='profile_view'),
    path('profile/edit/', views.profile_edit, name='profile_edit'),
    path('profile/favorites/', views.manage_favorites, name='manage_favorites'),
    path('match/<int:match_id>/', views.match_detail, name='match_detail'),
    path('news/<int:news_id>/', views.news_detail, name='news_detail'),
    path('match/<int:match_id>/pay/', views.payment_mock_view, name='payment_mock'),
    path('match/<int:match_id>/pay/process/', views.process_payment, name='process_payment'),
    path('my-tickets/', views.my_tickets, name='my_tickets'),
    path('ticket/download/<str:ticket_id>/', views.ticket_download_view, name='ticket_download'),
    path('my-teams/news/', views.fav_team_news, name='fav_team_news'),
    path('news/latest/', views.latest_news, name='latest_news'),
    path('feedback/', views.feedback_view, name='feedback'),
    path('admin-dashboard/feedback/', views.admin_feedback, name='admin_feedback'),
    path('admin-dashboard/feedback/delete/<int:feedback_id>/', views.admin_feedback_delete, name='admin_feedback_delete'),
    path('admin-dashboard/users/', views.admin_users, name='admin_users'),
    path('admin-dashboard/users/toggle/<int:user_id>/', views.toggle_user_status, name='toggle_user_status'),
    path('admin-dashboard/users/delete/<int:user_id>/', views.delete_user, name='delete_user'),
    path('admin-dashboard/analytics/', views.admin_analytics, name='admin_analytics'),
    path('admin-dashboard/cms/news/', views.admin_news_list, name='admin_news_list'),
    path('admin-dashboard/cms/news/add/', views.admin_news_create, name='admin_news_create'),
    path('admin-dashboard/cms/news/edit/<int:article_id>/', views.admin_news_edit, name='admin_news_edit'),
    path('admin-dashboard/cms/news/delete/<int:article_id>/', views.admin_news_delete, name='admin_news_delete'),
    path('admin-dashboard/organizer/create/', views.create_organizer, name='create_organizer'),
    path('admin-dashboard/settings/', views.system_settings, name='system_settings'),
    path('admin-dashboard/sync/', views.sync_sports_data, name='sync_sports_data'),
    path('admin-dashboard/sync-rosters/', views.sync_sports_rosters, name='sync_sports_rosters'),
    path('admin-dashboard/sync-news/', views.sync_sports_news, name='sync_sports_news'),
    path('admin-dashboard/transactions/', views.admin_transactions, name='admin_transactions'),
    path('search/', views.search_results, name='search_results'),
    path('community/', views.community_list, name='community_list'),
    path('community/create/', views.create_community, name='create_community'),
    path('community/request/<int:request_id>/<str:action>/', views.process_join_request, name='process_join_request'),
    path('community/<int:group_id>/remove/<int:user_id>/', views.remove_member, name='remove_member'),
    path('community/<int:group_id>/settings/<str:setting>/', views.toggle_community_setting, name='toggle_community_setting'),
    path('community/<int:group_id>/', views.community_detail, name='community_detail'),
    path('team/<int:team_id>/', views.team_detail, name='team_detail'),
    path('player/<int:player_id>/', views.player_detail, name='player_detail'),
    path('poll/vote/<int:poll_id>/', views.vote_poll, name='vote_poll'),
    path('organizer-dashboard/', views.organizer_dashboard, name='organizer_dashboard'),
    path('organizer-dashboard/events/', views.organizer_events_list, name='organizer_events_list'),
    path('organizer-dashboard/events/create/', views.organizer_event_create, name='organizer_event_create'),
    path('organizer-dashboard/profile/', views.organizer_profile, name='organizer_profile'),
    path('organizer/<str:username>/', views.public_organizer_profile, name='public_organizer_profile'),
    path('organizer-dashboard/events/edit/<int:match_id>/', views.organizer_event_edit, name='organizer_event_edit'),
    path('organizer-dashboard/events/delete/<int:match_id>/', views.organizer_event_delete, name='organizer_event_delete'),
    path('organizer-dashboard/events/polls/<int:match_id>/', views.organizer_polls, name='organizer_polls'),
    path('auth/change-password/', views.change_password_required, name='change_password_required'),
    path('ajax/load-teams/', views.load_teams, name='ajax_load_teams'),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
