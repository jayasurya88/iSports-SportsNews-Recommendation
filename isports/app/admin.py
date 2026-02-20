from django.contrib import admin
from .models import Team, Player, Match, Venue, UserProfile

@admin.register(UserProfile)
class UserProfileAdmin(admin.ModelAdmin):
    list_display = ('user', 'phone', 'dob', 'email_notifications', 'sms_notifications')
    search_fields = ('user__username', 'user__email', 'phone')
    list_filter = ('email_notifications', 'sms_notifications')

@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = ('name', 'city', 'capacity')
    search_fields = ('name', 'city')

@admin.register(Team)
class TeamAdmin(admin.ModelAdmin):
    list_display = ('name', 'league', 'venue', 'established_year')
    search_fields = ('name',)
    list_filter = ('league',)

@admin.register(Player)
class PlayerAdmin(admin.ModelAdmin):
    list_display = ('name', 'team', 'position', 'nationality')
    list_filter = ('team', 'position')
    search_fields = ('name',)

@admin.register(Match)
class MatchAdmin(admin.ModelAdmin):
    list_display = ('home_team', 'away_team', 'venue', 'date_time', 'status')
    list_filter = ('status', 'date_time', 'venue')
