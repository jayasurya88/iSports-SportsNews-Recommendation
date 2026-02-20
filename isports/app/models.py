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
    )
    home_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='home_matches')
    away_team = models.ForeignKey(Team, on_delete=models.CASCADE, related_name='away_matches')
    venue = models.ForeignKey(Venue, on_delete=models.SET_NULL, null=True, blank=True)
    league = models.CharField(max_length=100, blank=True, default='')
    date_time = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='scheduled')
    home_score = models.IntegerField(default=0)
    away_score = models.IntegerField(default=0)
    
    class Meta:
        verbose_name_plural = "Matches"

    def __str__(self):
        return f"{self.home_team} vs {self.away_team} at {self.date_time}"

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
    
    # Preference Engine Data
    favorite_teams = models.ManyToManyField(Team, blank=True, related_name='fans')
    
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
    source_url = models.URLField(max_length=1000)
    published_at = models.CharField(max_length=100, blank=True)
    category = models.CharField(max_length=100, default='Soccer')

    def __str__(self):
        return self.headline
