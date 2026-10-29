"""
Unit tests for email categorization covering all required categories and fallback.
"""
from app.services.classifier import classify_email, CATEGORIES


def test_classify_academics_and_assignments():
    cat = classify_email("CS101 Homework 4 Submission", "Please submit your problem set solutions by Friday.")
    assert cat == "Academics and assignments"


def test_classify_examinations_and_results():
    cat = classify_email("Midterm Exam Schedule & Hall Ticket", "Find your admit card and examination room details.")
    assert cat == "Examinations and results"


def test_classify_placements_and_internships():
    cat = classify_email("Google Campus Placement Drive 2026", "Shortlisted students for software engineering interview.")
    assert cat == "Placements and internships"


def test_classify_fees_and_payments():
    cat = classify_email("Tuition Fee Due Notice", "Your semester fee payment is pending with outstanding dues.")
    assert cat == "Fees and payments"


def test_classify_meetings_and_events():
    cat = classify_email("Faculty Townhall & Annual Symposium", "Join the zoom link for our quarterly meeting.")
    assert cat == "Meetings and events"


def test_classify_bills_and_receipts():
    cat = classify_email("Invoice #40291 Payment Confirmation", "Your credit card statement and order receipt are attached.")
    assert cat == "Bills and receipts"


def test_classify_travel_and_bookings():
    cat = classify_email("Flight Itinerary & Boarding Pass", "Your airline booking confirmation and PNR details.")
    assert cat == "Travel and bookings"


def test_classify_newsletters_and_promotions():
    cat = classify_email("Weekly Tech Digest & Special Offer", "Click here to unsubscribe from this promotional roundup.")
    assert cat == "Newsletters and promotions"


def test_classify_security_alerts():
    cat = classify_email("Security Alert: New Login Detected", "Your two-factor verification code (2FA) is 921048.")
    assert cat == "Security alerts"


def test_classify_unrelated_defaults_to_other():
    cat = classify_email("Random thoughts", "Just some abstract poetry with zero keywords.")
    assert cat == "Other"
    assert cat in CATEGORIES

