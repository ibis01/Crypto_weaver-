"""
Multi-channel Notification System
"""
import smtplib
import requests
from typing import List, Dict, Any
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
import json
from datetime import datetime


class NotificationChannel:
    """Base notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        self.config = config
    
    def send(self, message: str, recipient: str, **kwargs) -> bool:
        """Send notification"""
        raise NotImplementedError("Subclasses must implement send()")
    
    def format_message(self, alert_data: Dict[str, Any]) -> str:
        """Format alert data into notification message"""
        alert_name = alert_data.get('alert_name', 'Unknown Alert')
        symbol = alert_data.get('symbol', 'Unknown')
        price = alert_data.get('price', 0)
        trigger_time = alert_data.get('trigger_time', datetime.utcnow())
        
        return f"""
🚨 ALERT TRIGGERED: {alert_name}
📈 Symbol: {symbol}
💰 Price: ${price:,.2f}
⏰ Time: {trigger_time.strftime('%Y-%m-%d %H:%M:%S UTC')}
🔔 Condition: {alert_data.get('condition', 'N/A')}
📊 Additional Data: {json.dumps(alert_data.get('additional_data', {}), indent=2)}
"""


class EmailNotifier(NotificationChannel):
    """Email notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.smtp_server = config.get('smtp_server', 'smtp.gmail.com')
        self.smtp_port = config.get('smtp_port', 587)
        self.smtp_username = config.get('smtp_username')
        self.smtp_password = config.get('smtp_password')
        self.from_email = config.get('from_email')
    
    def send(self, message: str, recipient: str, subject: str = "Crypto Alert") -> bool:
        """Send email notification"""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.from_email
            msg['To'] = recipient
            msg['Subject'] = subject
            
            msg.attach(MIMEText(message, 'plain'))
            
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.smtp_username, self.smtp_password)
            server.send_message(msg)
            server.quit()
            
            return True
        except Exception as e:
            print(f"Email sending failed: {e}")
            return False


class WebhookNotifier(NotificationChannel):
    """Webhook notification channel"""
    
    def send(self, message: str, recipient: str, **kwargs) -> bool:
        """Send webhook notification"""
        try:
            payload = {
                'message': message,
                'timestamp': datetime.utcnow().isoformat(),
                'data': kwargs.get('alert_data', {})
            }
            
            headers = {
                'Content-Type': 'application/json',
                'User-Agent': 'CryptoWeaver-Alerts/1.0'
            }
            
            # Add custom headers if provided
            custom_headers = self.config.get('headers', {})
            headers.update(custom_headers)
            
            response = requests.post(
                recipient,
                json=payload,
                headers=headers,
                timeout=10
            )
            
            return response.status_code in [200, 201, 202]
            
        except Exception as e:
            print(f"Webhook sending failed: {e}")
            return False


class DiscordNotifier(NotificationChannel):
    """Discord notification channel"""
    
    def format_message(self, alert_data: Dict[str, Any]) -> str:
        """Format for Discord embed"""
        embed = {
            "title": f"🚨 {alert_data.get('alert_name', 'Alert Triggered')}",
            "description": f"**Symbol**: {alert_data.get('symbol', 'Unknown')}",
            "color": 0xff0000,  # Red
            "fields": [
                {"name": "Price", "value": f"${alert_data.get('price', 0):,.2f}", "inline": True},
                {"name": "Condition", "value": alert_data.get('condition', 'N/A'), "inline": True},
                {"name": "Time", "value": alert_data.get('trigger_time', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S UTC'), "inline": True},
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
        
        # Add additional data as fields
        additional_data = alert_data.get('additional_data', {})
        for key, value in additional_data.items():
            if key not in ['alert_name', 'symbol', 'price', 'condition', 'trigger_time']:
                embed["fields"].append({
                    "name": key.replace('_', ' ').title(),
                    "value": str(value)[:100] + ("..." if len(str(value)) > 100 else ""),
                    "inline": True
                })
        
        return json.dumps({"embeds": [embed]})
    
    def send(self, message: str, recipient: str, **kwargs) -> bool:
        """Send Discord webhook notification"""
        try:
            # Check if message is already JSON (embed format)
            try:
                payload = json.loads(message)
            except json.JSONDecodeError:
                # Plain text message
                payload = {"content": message}
            
            headers = {'Content-Type': 'application/json'}
            response = requests.post(recipient, json=payload, headers=headers, timeout=10)
            
            return response.status_code in [200, 201, 204]
            
        except Exception as e:
            print(f"Discord webhook failed: {e}")
            return False


class TelegramNotifier(NotificationChannel):
    """Telegram notification channel"""
    
    def __init__(self, config: Dict[str, Any]):
        super().__init__(config)
        self.bot_token = config.get('bot_token')
        self.chat_id = config.get('chat_id')
    
    def send(self, message: str, recipient: str = None, **kwargs) -> bool:
        """Send Telegram notification"""
        try:
            chat_id = recipient or self.chat_id
            if not chat_id:
                raise ValueError("Telegram chat_id not provided")
            
            url = f"https://api.telegram.org/bot{self.bot_token}/sendMessage"
            payload = {
                'chat_id': chat_id,
                'text': message,
                'parse_mode': 'HTML'
            }
            
            response = requests.post(url, json=payload, timeout=10)
            return response.status_code == 200
            
        except Exception as e:
            print(f"Telegram notification failed: {e}")
            return False


class NotificationManager:
    """Manager for multi-channel notifications"""
    
    def __init__(self):
        self.channels = {}
        self.notification_history = []
    
    def register_channel(self, name: str, channel: NotificationChannel):
        """Register a notification channel"""
        self.channels[name] = channel
    
    def send_notification(self, alert_data: Dict[str, Any], 
                         channels: List[str] = None,
                         recipients: Dict[str, List[str]] = None) -> Dict[str, bool]:
        """Send notification through multiple channels"""
        results = {}
        message = self._format_alert_message(alert_data)
        
        # Default to all channels if none specified
        if channels is None:
            channels = list(self.channels.keys())
        
        for channel_name in channels:
            if channel_name not in self.channels:
                results[channel_name] = False
                continue
            
            channel = self.channels[channel_name]
            channel_recipients = (recipients or {}).get(channel_name, [])
            
            if not channel_recipients:
                # Try default recipients from channel config
                if hasattr(channel, 'default_recipient'):
                    channel_recipients = [channel.default_recipient]
                else:
                    results[channel_name] = False
                    continue
            
            # Format message for specific channel if needed
            if hasattr(channel, 'format_message'):
                channel_message = channel.format_message(alert_data)
            else:
                channel_message = message
            
            # Send to all recipients
            success = True
            for recipient in channel_recipients:
                try:
                    sent = channel.send(channel_message, recipient, alert_data=alert_data)
                    if not sent:
                        success = False
                except Exception as e:
                    print(f"Error sending {channel_name} to {recipient}: {e}")
                    success = False
            
            results[channel_name] = success
            
            # Record in history
            self.notification_history.append({
                'timestamp': datetime.utcnow(),
                'channel': channel_name,
                'alert_data': alert_data,
                'success': success,
                'recipients': channel_recipients
            })
        
        return results
    
    def _format_alert_message(self, alert_data: Dict[str, Any]) -> str:
        """Format alert data into readable message"""
        template = """
🚨 ALERT: {alert_name}
📈 {symbol} - ${price:,.2f}
⏰ {time}
📊 Condition: {condition}
"""
        
        return template.format(
            alert_name=alert_data.get('alert_name', 'Unknown'),
            symbol=alert_data.get('symbol', 'Unknown'),
            price=alert_data.get('price', 0),
            time=alert_data.get('trigger_time', datetime.utcnow()).strftime('%Y-%m-%d %H:%M:%S UTC'),
            condition=alert_data.get('condition', 'N/A')
        )
    
    def get_stats(self, hours: int = 24) -> Dict[str, Any]:
        """Get notification statistics"""
        cutoff = datetime.utcnow() - timedelta(hours=hours)
        recent = [n for n in self.notification_history if n['timestamp'] > cutoff]
        
        stats = {
            'total_notifications': len(recent),
            'by_channel': {},
            'success_rate': 0,
            'failed_notifications': 0
        }
        
        if not recent:
            return stats
        
        success_count = sum(1 for n in recent if n['success'])
        stats['success_rate'] = (success_count / len(recent)) * 100
        stats['failed_notifications'] = len(recent) - success_count
        
        # Count by channel
        for notification in recent:
            channel = notification['channel']
            if channel not in stats['by_channel']:
                stats['by_channel'][channel] = {'total': 0, 'success': 0}
            
            stats['by_channel'][channel]['total'] += 1
            if notification['success']:
                stats['by_channel'][channel]['success'] += 1
        
        return stats
