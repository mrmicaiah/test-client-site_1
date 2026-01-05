"""
Settings routes - business info, Google Calendar connection.
"""
from flask import Blueprint, render_template, request, redirect, url_for, flash, current_app, session
import requests
from urllib.parse import urlencode
from datetime import datetime, timedelta
import os
from ..auth import login_required, get_current_user_id, get_user_profile
from ..supabase_client import get_supabase

bp = Blueprint('settings', __name__, url_prefix='/settings')

# Google OAuth settings
GOOGLE_AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_SCOPES = "https://www.googleapis.com/auth/calendar.events"


@bp.route('/')
@login_required
def index():
    """Settings page."""
    profile = get_user_profile()
    user_email = session.get('user_email', '')
    
    return render_template('settings/index.html', 
                           profile=profile,
                           user_email=user_email)


@bp.route('/business', methods=['GET', 'POST'])
@login_required
def business_info():
    """Edit business information."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        business_name = request.form.get('business_name', '').strip() or None
        business_phone = request.form.get('business_phone', '').strip() or None
        
        try:
            supabase.table('user_profiles').update({
                'business_name': business_name,
                'business_phone': business_phone
            }).eq('id', user_id).execute()
            
            flash('Business information updated.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to update business information.', 'error')
    
    return render_template('settings/business.html', profile=profile)


@bp.route('/payment', methods=['GET', 'POST'])
@login_required
def payment_instructions():
    """Edit payment instructions."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        payment_instructions = request.form.get('payment_instructions', '').strip() or None
        
        try:
            supabase.table('user_profiles').update({
                'payment_instructions': payment_instructions
            }).eq('id', user_id).execute()
            
            flash('Payment instructions updated.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to update payment instructions.', 'error')
    
    return render_template('settings/payment.html', profile=profile)


@bp.route('/logo', methods=['GET', 'POST'])
@login_required
def upload_logo():
    """Upload business logo."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    profile = get_user_profile()
    
    if request.method == 'POST':
        if 'logo' not in request.files:
            flash('No file selected.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        file = request.files['logo']
        
        if file.filename == '':
            flash('No file selected.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        # Check file type
        allowed_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        file_ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
        
        if file_ext not in allowed_extensions:
            flash('Please upload a PNG, JPG, or GIF image.', 'error')
            return redirect(url_for('settings.upload_logo'))
        
        try:
            # Read file data
            file_data = file.read()
            
            # Upload to Supabase Storage
            path = f"logos/{user_id}/logo.{file_ext}"
            
            # Delete old logo if exists
            try:
                supabase.storage.from_('miklean-files').remove([path])
            except:
                pass
            
            # Upload new logo
            supabase.storage.from_('miklean-files').upload(
                path,
                file_data,
                {'content-type': f'image/{file_ext}'}
            )
            
            # Get public URL
            logo_url = supabase.storage.from_('miklean-files').get_public_url(path)
            
            # Update profile
            supabase.table('user_profiles').update({
                'business_logo_url': logo_url
            }).eq('id', user_id).execute()
            
            flash('Logo uploaded.', 'success')
            return redirect(url_for('settings.index'))
            
        except Exception as e:
            flash('Failed to upload logo. Please try again.', 'error')
    
    return render_template('settings/logo.html', profile=profile)


@bp.route('/google/connect')
@login_required
def google_connect():
    """Start Google OAuth flow for Calendar access."""
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    
    if not client_id:
        flash('Google Calendar not configured.', 'error')
        return redirect(url_for('settings.index'))
    
    # Build OAuth URL
    redirect_uri = url_for('settings.google_callback', _external=True)
    
    params = {
        'client_id': client_id,
        'redirect_uri': redirect_uri,
        'response_type': 'code',
        'scope': GOOGLE_SCOPES,
        'access_type': 'offline',
        'prompt': 'consent'
    }
    
    auth_url = f"{GOOGLE_AUTH_URL}?{urlencode(params)}"
    return redirect(auth_url)


@bp.route('/google/callback')
@login_required
def google_callback():
    """Handle Google OAuth callback."""
    code = request.args.get('code')
    error = request.args.get('error')
    
    if error:
        flash(f'Google authorization failed: {error}', 'error')
        return redirect(url_for('settings.index'))
    
    if not code:
        flash('No authorization code received.', 'error')
        return redirect(url_for('settings.index'))
    
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    redirect_uri = url_for('settings.google_callback', _external=True)
    
    # Exchange code for tokens
    token_data = {
        'code': code,
        'client_id': client_id,
        'client_secret': client_secret,
        'redirect_uri': redirect_uri,
        'grant_type': 'authorization_code'
    }
    
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        tokens = response.json()
        
        if 'error' in tokens:
            flash(f'Failed to get access token: {tokens.get("error_description", tokens["error"])}', 'error')
            return redirect(url_for('settings.index'))
        
        access_token = tokens.get('access_token')
        refresh_token = tokens.get('refresh_token')
        expires_in = tokens.get('expires_in', 3600)
        
        # Calculate expiry time
        expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Save tokens to user profile
        user_id = get_current_user_id()
        supabase = get_supabase()
        
        supabase.table('user_profiles').update({
            'google_access_token': access_token,
            'google_refresh_token': refresh_token,
            'google_token_expiry': expiry.isoformat()
        }).eq('id', user_id).execute()
        
        flash('Google Calendar connected!', 'success')
        
    except Exception as e:
        flash('Failed to connect Google Calendar.', 'error')
    
    return redirect(url_for('settings.index'))


@bp.route('/google/disconnect', methods=['POST'])
@login_required
def google_disconnect():
    """Disconnect Google Calendar."""
    user_id = get_current_user_id()
    supabase = get_supabase()
    
    try:
        supabase.table('user_profiles').update({
            'google_access_token': None,
            'google_refresh_token': None,
            'google_token_expiry': None,
            'google_calendar_id': None
        }).eq('id', user_id).execute()
        
        flash('Google Calendar disconnected.', 'success')
        
    except Exception as e:
        flash('Failed to disconnect Google Calendar.', 'error')
    
    return redirect(url_for('settings.index'))


def get_valid_google_token(user_id):
    """Get a valid Google access token, refreshing if needed."""
    supabase = get_supabase()
    
    response = supabase.table('user_profiles').select(
        'google_access_token, google_refresh_token, google_token_expiry'
    ).eq('id', user_id).single().execute()
    
    if not response.data:
        return None
    
    profile = response.data
    access_token = profile.get('google_access_token')
    refresh_token = profile.get('google_refresh_token')
    expiry_str = profile.get('google_token_expiry')
    
    if not access_token or not refresh_token:
        return None
    
    # Check if token is expired
    if expiry_str:
        expiry = datetime.fromisoformat(expiry_str.replace('Z', '+00:00'))
        if datetime.utcnow() < expiry - timedelta(minutes=5):
            return access_token
    
    # Token expired, refresh it
    client_id = os.environ.get('GOOGLE_CLIENT_ID')
    client_secret = os.environ.get('GOOGLE_CLIENT_SECRET')
    
    token_data = {
        'client_id': client_id,
        'client_secret': client_secret,
        'refresh_token': refresh_token,
        'grant_type': 'refresh_token'
    }
    
    try:
        response = requests.post(GOOGLE_TOKEN_URL, data=token_data)
        tokens = response.json()
        
        if 'error' in tokens:
            return None
        
        new_access_token = tokens.get('access_token')
        expires_in = tokens.get('expires_in', 3600)
        new_expiry = datetime.utcnow() + timedelta(seconds=expires_in)
        
        # Save new token
        supabase.table('user_profiles').update({
            'google_access_token': new_access_token,
            'google_token_expiry': new_expiry.isoformat()
        }).eq('id', user_id).execute()
        
        return new_access_token
        
    except:
        return None


def create_calendar_event(user_id, visit):
    """Create a Google Calendar event for a visit."""
    access_token = get_valid_google_token(user_id)
    
    if not access_token:
        return False
    
    # Build event data
    event = {
        'summary': f"Cleaning - {visit.get('client_name', 'Client')}",
        'location': visit.get('client_address', ''),
        'description': f"MiKlean cleaning visit\n\nNotes: {visit.get('notes', 'None')}",
        'start': {
            'date': visit['scheduled_date']
        },
        'end': {
            'date': visit['scheduled_date']
        }
    }
    
    # If time is specified, use dateTime instead of date
    if visit.get('scheduled_time'):
        start_datetime = f"{visit['scheduled_date']}T{visit['scheduled_time']}"
        end_datetime = f"{visit['scheduled_date']}T{visit['scheduled_time']}"  # 1 hour later ideally
        event['start'] = {'dateTime': start_datetime, 'timeZone': 'America/New_York'}
        event['end'] = {'dateTime': end_datetime, 'timeZone': 'America/New_York'}
    
    try:
        response = requests.post(
            'https://www.googleapis.com/calendar/v3/calendars/primary/events',
            headers={
                'Authorization': f'Bearer {access_token}',
                'Content-Type': 'application/json'
            },
            json=event
        )
        
        if response.status_code == 200:
            event_data = response.json()
            return event_data.get('id')
        else:
            return False
            
    except:
        return False


def delete_calendar_event(user_id, event_id):
    """Delete a Google Calendar event."""
    access_token = get_valid_google_token(user_id)
    
    if not access_token or not event_id:
        return False
    
    try:
        response = requests.delete(
            f'https://www.googleapis.com/calendar/v3/calendars/primary/events/{event_id}',
            headers={'Authorization': f'Bearer {access_token}'}
        )
        return response.status_code == 204
    except:
        return False
