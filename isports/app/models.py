from django.db import models
from django.contrib.auth.models import User

# Create your models here.
class Venue(models.Model):
    name = models.CharField(max_length=200)
    city = models.CharField(max_length=100)
    capacity = models.IntegerField(default=0)
    image = models.ImageField(upload_to='venues/', blank=True, null=True)

    def __str__(self):
        return self.name

class Team(models.Model):
    name = models.CharField(max_length=100)
    logo = models.ImageField(upload_to='teams/', blank=True, null=True)
    sport = models.CharField(max_length=50, default="Football")
    league = models.CharField(max_length=100, default="Unknown League")
    description = models.TextField(blank=True)
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    established_year = models.IntegerField(null=True, blank=True)

    def __str__(self):
        return self.name

class Player(models.Model):
    name = models.CharField(max_length=100)
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='players')
    position = models.CharField(max_length=50)
    photo_url = models.URLField(blank=True, null=True)
    nationality = models.CharField(max_length=100, blank=True)
    dob = models.DateField(null=True, blank=True)

    def __str__(self):
        return self.name

class Match(models.Model):
    STATUS_CHOICES = (
        ('scheduled', 'Scheduled'),
        ('live', 'Live'),
        ('finished', 'Finished'),
        ('postponed', 'Postponed'),
        ('cancelled', 'Cancelled'),
    )
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    league = models.CharField(max_length=100, blank=True, default='')
    date_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    
    # Event Management Fields
    organizer = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True, related_name='organized_matches')
    lineups = models.TextField(blank=True, help_text="Lineup details")
    injury_news = models.TextField(blank=True)
    pre_game_insights = models.TextField(blank=True)
    highlights_url = models.URLField(blank=True, null=True)
    exclusive_media = models.FileField(upload_to='match_media/', blank=True, null=True)
    ticket_price = models.DecimalField(max_digits=10, decimal_places=2, default=50.00)
    match_events = models.TextField(blank=True, help_text="List scorers and match events (e.g., Goal: Player Name 23')")
    
    class Meta:
        verbose_name_plural = "Matches"

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} at {self.date_time}"

class CommunityGroup(models.Model):
    name = models.CharField(max_length=200)
    description = models.TextField()
    team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='fan_groups', null=True, blank=True)
    league = models.CharField(max_length=100, blank=True)
    creator = models.ForeignKey(User, on_delete=models.CASCADE, related_name='created_communities')
    members = models.ManyToManyField(User, related_name='joined_communities')
    
    # New Settings
    is_public = models.BooleanField(default=True, help_text="If false, only members can see chats")
    require_approval = models.BooleanField(default=False, help_text="If true, users must request to join")
    
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

class CommunityMessage(models.Model):
    group = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name='messages')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} in {self.group.name}"

class CommunityJoinRequest(models.Model):
    group = models.ForeignKey(CommunityGroup, on_delete=models.CASCADE, related_name='join_requests')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    status = models.CharField(max_length=20, choices=[('pending', 'Pending'), ('approved', 'Approved'), ('rejected', 'Rejected')], default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} request for {self.group.name}"

class Poll(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='polls')
    question = models.CharField(max_length=300)
    option_a = models.CharField(max_length=100)
    option_b = models.CharField(max_length=100)
    votes_a = models.IntegerField(default=0)
    votes_b = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)

    def total_votes(self):
        return self.votes_a + self.votes_b

    def percentage_a(self):
        total = self.total_votes()
        if total == 0: return 0
        return int((self.votes_a / total) * 100)

    def percentage_b(self):
        total = self.total_votes()
        if total == 0: return 0
        return int((self.votes_b / total) * 100)

    def __str__(self):
        return self.question

class PollVote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name='user_votes')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    choice = models.CharField(max_length=1) # 'a' or 'b'
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        unique_together = ('poll', 'user')

    def __str__(self):
        return f"{self.user.username} voted on {self.poll.question}"

class Alert(models.Model):
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='alerts')
    message = models.TextField()
    alert_type = models.CharField(max_length=50) # 'modification', 'cancellation', 'live_update'
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.alert_type} - {self.match}"

class Ticket(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tickets')
    match = models.ForeignKey(Match, on_delete=models.CASCADE, related_name='tickets')
    purchase_date = models.DateTimeField(auto_now_add=True)
    quantity = models.PositiveIntegerField(default=1)
    total_price = models.DecimalField(max_digits=10, decimal_places=2)
    seat_section = models.CharField(max_length=50, default='General')
    ticket_id = models.CharField(max_length=20, unique=True)
    status = models.CharField(max_length=20, default='active') # active, used, cancelled

    def __str__(self):
        return f"Ticket {self.ticket_id} - {self.user.username}"

class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    phone = models.CharField(max_length=20, blank=True, null=True)
    dob = models.DateField(blank=True, null=True)
    profile_picture = models.ImageField(upload_to='profile_pics/', blank=True, null=True)
    
    # Roles: 'admin', 'organizer', 'user'
    ROLE_CHOICES = [
        ('admin', 'Admin'),
        ('organizer', 'Organizer'),
        ('user', 'User'),
    ]
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    needs_password_change = models.BooleanField(default=False)
    onboarding_completed = models.BooleanField(default=False)
    view_password = models.CharField(max_length=128, blank=True, null=True) # For admin visibility (Dev only)
    
    # Preference Engine Data
    interests = models.TextField(blank=True, help_text="Comma separated sports interests")
    favorite_teams = models.ManyToManyField(Team, blank=True, related_name='fans')
    
    is_premium = models.BooleanField(default=False)
    
    # Notification Settings
    email_notifications = models.BooleanField(default=True)
    sms_notifications = models.BooleanField(default=False)
    
    def __str__(self):
        return self.user.username

class NewsArticle(models.Model):
    headline = models.CharField(max_length=500)
    summary = models.TextField(blank=True)
    content = models.TextField(blank=True)
    image_url = models.URLField(max_length=1000, blank=True, null=True)
    image_file = models.ImageField(upload_to='news_articles/', blank=True, null=True)
    source_url = models.URLField(max_length=1000, blank=True)
    published_at = models.DateTimeField(null=True, blank=True)
    category = models.CharField(max_length=100, default='Soccer')

    def __str__(self):
        return self.headline

class Feedback(models.Model):
    user = models.ForeignKey(User, on_delete=models.CASCADE, null=True, blank=True)
    subject = models.CharField(max_length=200)
    message = models.TextField()
    rating = models.IntegerField(default=5)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Feedback from {self.user.username if self.user else 'Anonymous'} - {self.subject}"
