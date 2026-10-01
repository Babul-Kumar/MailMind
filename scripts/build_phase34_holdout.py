"""
Phase 34: Build modern_email_holdout_v2.csv (100+ rows) and run full evaluation.
"""
import csv, json, sys, os
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

HOLDOUT_ROWS = [
    # OTP / login verification (P1, action=True)
    ("mh001","Google: Your sign-in verification code","Your sign-in code is 482913. It expires in 10 minutes. Never share this code with anyone.","P1","True","otp_auth"),
    ("mh002","Apple ID: Verification code","482 051 is your Apple ID verification code. Do not share it with anyone.","P1","True","otp_auth"),
    ("mh003","Figma: Your one-time login code","Use code 918274 to verify your identity on Figma. This code is valid for 5 minutes.","P1","True","otp_auth"),
    ("mh004","Atlassian: Your Jira verification code","Enter 776241 to complete signing in to Jira. Code expires in 10 minutes.","P1","True","otp_auth"),
    ("mh005","Slack: Confirm your email address","Your Slack verification code is 392014. The code expires in 15 minutes.","P1","True","otp_auth"),
    ("mh006","Zoom: Your verification code","Your Zoom verification code is 204817. Please enter this code to continue. Valid for 5 minutes.","P1","True","otp_auth"),
    ("mh007","LinkedIn: Email verification code","Please use the verification code 839201 to confirm your LinkedIn account. Expires in 10 minutes.","P1","True","otp_auth"),
    ("mh008","Dropbox: Security code","Your Dropbox security code is 574831. Enter this code to verify your account. This code is only valid for 10 minutes.","P1","True","otp_auth"),
    ("mh009","Microsoft: Security code","Please use security code 310928 to verify your Microsoft account sign-in. Code expires in 5 minutes.","P1","True","otp_auth"),
    ("mh010","Twitter: Confirm your account","Your Twitter confirmation code is 908321. Enter the code on the web browser where you started the sign-up process.","P1","True","otp_auth"),
    # MFA / 2FA (P1)
    ("mh011","AWS: Multi-factor authentication code","Your AWS multi-factor authentication code is 728391. Enter this code to sign in. Code expires in 30 seconds.","P1","True","otp_auth"),
    ("mh012","GitHub: Authentication code","Your GitHub authentication code is 563821. Do not share this code. Code valid for 30 seconds.","P1","True","otp_auth"),
    ("mh013","Okta: One-time passcode","Your one-time passcode is 641927. Enter this code to complete authentication. Valid for 10 minutes.","P1","True","otp_auth"),
    ("mh014","Duo: Two-factor authentication","Your Duo two-factor code is 293716. Enter this code in your login page. Expires in 2 minutes.","P1","True","otp_auth"),
    ("mh015","Authy: Verification code","Your Authy verification token is 829130. Enter this code to complete your two-factor authentication.","P1","True","otp_auth"),
    # Password reset (P1)
    ("mh016","Reset your Netflix password","We received a request to reset your Netflix password. Use code 391827 to continue. This link expires in 1 hour.","P1","True","password_reset"),
    ("mh017","Reddit: Reset your password","We got a request to reset your Reddit password. Click this link within 24 hours to reset your password.","P1","True","password_reset"),
    ("mh018","Shopify: Password reset request","You requested a password reset for your Shopify account. This link will expire in 20 minutes.","P1","True","password_reset"),
    ("mh019","Spotify: Request to change your password","A password change request was made for your account. This link expires in 24 hours.","P1","True","password_reset"),
    ("mh020","Canva: Reset your password","Someone requested a password reset for the Canva account. Use code 736294 within 30 minutes to reset it.","P1","True","password_reset"),
    # Security alerts actionable (P1)
    ("mh021","New sign-in to your Google account","A new sign-in to your Google Account was detected. If this was not you, secure your account now.","P1","True","security_alert"),
    ("mh022","Unusual login attempt detected","We noticed a login from an unrecognized device in Singapore. If this was not you, change your password immediately.","P1","True","security_alert"),
    ("mh023","Alert: Your account password was changed","Your account password was changed. If you did not make this change, contact support and reset your password immediately.","P1","True","security_alert"),
    ("mh024","Suspicious activity on your bank account","We detected unusual activity. Please review your recent transactions and report any unrecognized charges immediately.","P1","True","security_alert"),
    ("mh025","Action required: Unauthorized API access attempt","Your API key was used from an unrecognized IP. Please rotate your credentials immediately.","P1","True","security_alert"),
    # Non-actionable security (P3/P4)
    ("mh026","Your security settings were updated","This is a confirmation that your two-factor authentication settings were successfully updated. No further action is required.","P3","False","security_info"),
    ("mh027","Monthly account security summary","Here is your security summary for September. All login attempts were from recognized devices. No suspicious activity detected.","P4","False","security_info"),
    ("mh028","Your account was verified successfully","Your identity has been successfully verified. You now have full access to your account.","P3","False","security_info"),
    ("mh029","Your account verification was completed","Your application verification was completed on October 1st. Your account is now fully active.","P3","False","security_info"),
    ("mh030","Previous login verification was successful","Your recent login verification was completed successfully. No further steps are required.","P4","False","security_info"),
    # Payment failures / billing (P1-P2)
    ("mh031","Payment failed: Update your payment method","Your payment for Plan Pro ($49/month) failed. Please update your payment method to avoid service interruption. Grace period ends Oct 5.","P1","True","payments"),
    ("mh032","Invoice overdue: Immediate payment required","Invoice #12849 for $899 is now 30 days overdue. Please settle this invoice to avoid suspension.","P1","True","payments"),
    ("mh033","Subscription expiring in 3 days","Your Pro subscription expires on Oct 5. Renew now to continue accessing premium features.","P2","True","payments"),
    ("mh034","Your payment was declined","We were unable to process your payment of $19.99. Please update your billing information.","P2","True","payments"),
    ("mh035","Card ending in 4821 will expire next month","Your payment card on file will expire next month. Please update your payment method before your next billing cycle.","P2","True","payments"),
    # Payment confirmations (P3/P4)
    ("mh036","Payment received: Thank you","We received your payment of $49.00 for your monthly plan. Your subscription is active through November 1, 2026.","P4","False","payments"),
    ("mh037","Your order has been confirmed","Order #729104 has been placed successfully. Estimated delivery: Oct 7-9.","P4","False","payments"),
    # Deadlines (P1-P2)
    ("mh038","Final reminder: Application deadline tomorrow","This is your final reminder that the application deadline for the Spring cohort is tomorrow at 11:59 PM. Submit now.","P1","True","deadlines"),
    ("mh039","Tax filing deadline approaching","Your estimated tax payment is due on October 15. Please file before the deadline to avoid penalties.","P1","True","deadlines"),
    ("mh040","Assignment submission closes in 2 hours","Your Assignment 5 submission window closes in 2 hours. Submit your work before 11:59 PM IST.","P1","True","deadlines"),
    ("mh041","Grant application deadline: 5 days left","Your application for the research grant must be submitted by October 7, 2026. Ensure all documents are uploaded.","P2","True","deadlines"),
    ("mh042","Internship offer: Accept by Friday","Congratulations on your internship offer from Infosys. Please accept or decline by this Friday, October 4.","P2","True","deadlines"),
    ("mh043","Conference paper deadline: 7 days","The submission deadline for the IEEE International Conference is October 9, 2026. Please submit your paper.","P2","True","deadlines"),
    # Recruitment (P1-P2)
    ("mh044","Interview invitation: Software Engineer at Google","Congratulations! We would like to invite you for a technical interview. Please select your available slots.","P1","True","recruitment"),
    ("mh045","Action required: Complete your application profile","Your job application is 80% complete. Please submit the remaining documents before the position closes October 10.","P1","True","recruitment"),
    ("mh046","Your application has been reviewed","Thank you for applying to Amazon. Your application is under review. We will contact you within 2 weeks.","P2","False","recruitment"),
    ("mh047","Coding assessment invitation: 48-hour window","You have been invited to complete a coding assessment for the Backend Engineer role. The test link is active for 48 hours.","P1","True","recruitment"),
    ("mh048","Offer letter enclosed: Please review and respond","Please find your offer letter for the Data Scientist position attached. We require your response by October 6, 2026.","P1","True","recruitment"),
    ("mh049","Application shortlisted: Next round details","Your application has been shortlisted. Please confirm your availability for October 8 or 9.","P2","True","recruitment"),
    # SaaS (mixed)
    ("mh050","Your free trial ends in 3 days","Your 14-day free trial of Notion Pro expires on October 5. Upgrade now to continue using premium features.","P2","True","saas"),
    ("mh051","Action required: Verify your domain ownership","Domain verification is required. Add the TXT record within 72 hours or verification will time out.","P1","True","saas"),
    ("mh052","Your API usage limit has been reached","You have reached 100% of your monthly API quota. Requests will be rejected until the limit resets.","P2","True","saas"),
    ("mh053","Scheduled maintenance: Oct 5 2am-4am","Scheduled maintenance on October 5 between 2:00 AM and 4:00 AM UTC. Services may be unavailable.","P3","False","saas"),
    ("mh054","New feature announcement: AI assistant launched","We are excited to announce our AI assistant feature. Sign in to try it out today.","P4","False","saas"),
    ("mh055","Your export is ready to download","Your data export is ready. Download it before October 15 as exports are deleted after 14 days.","P3","False","saas"),
    ("mh056","Integration disconnected: Slack workspace","Your Slack integration was disconnected due to a token expiry. Please reconnect to restore automation.","P2","True","saas"),
    ("mh057","Service disruption resolved","Our database service disruption has been resolved. All services are now operating normally.","P4","False","saas"),
    # Academic (mixed)
    ("mh058","Exam schedule released: Mid-semester exams","The mid-semester examination schedule has been released. Please review the schedule and note your exam timings.","P2","False","academic"),
    ("mh059","Fee payment deadline: October 10","Your semester fee payment is due by October 10. Late payments will incur a penalty of 2% per week.","P1","True","academic"),
    ("mh060","Assignment 3 grades posted","Your grades for Assignment 3 have been posted on the student portal. Review your feedback before next submission.","P3","False","academic"),
    ("mh061","NPTEL: Week 5 quiz deadline","Week 5 quiz for your NPTEL course closes on October 7 at 23:59. Complete it before the deadline.","P2","True","academic"),
    ("mh062","Library book overdue: Fine accumulating","The book you borrowed was due on September 28. A fine of Rs 5/day is accumulating. Please return it.","P2","True","academic"),
    ("mh063","Internship completion certificate ready","Your internship completion certificate has been generated and is available for download on the portal.","P3","False","academic"),
    ("mh064","Thesis submission portal is now open","The thesis submission portal for December graduates is now open. Submissions accepted until November 30, 2026.","P2","True","academic"),
    # Newsletters / promotions (P4)
    ("mh065","This week in tech: AI models and more","Welcome to this week's edition of The Rundown. We cover the latest in AI research, startup funding, and big tech.","P4","False","newsletter"),
    ("mh066","Your weekly digest from Stack Overflow","Here is your weekly digest including most-voted questions in Python, JavaScript, and system design.","P4","False","newsletter"),
    ("mh067","Flash sale: 50% off all premium plans today only","Today only: 50% off all our premium annual plans! Use code FLASH50 at checkout. Offer expires at midnight.","P4","False","promotional"),
    ("mh068","Introducing: New premium features for subscribers","We are excited to share new premium features now available for all subscribers. Sign in to explore.","P4","False","newsletter"),
    ("mh069","Monthly product newsletter from Notion","Here is what is new in Notion this month: kanban improvements, templates gallery updates, and API v2 beta.","P4","False","newsletter"),
    ("mh070","Top 5 productivity tools for remote teams","Boost your team's productivity with these five tools. Read the full guide on our blog.","P4","False","newsletter"),
    ("mh071","Your weekly job recommendations","Based on your profile, here are 12 new job openings matching your skills in Python, ML, and cloud.","P3","False","newsletter"),
    ("mh072","Exclusive offer: Upgrade to annual for 30% savings","Switch to an annual plan and save 30% on your current rate. Offer valid until October 31, 2026.","P4","False","promotional"),
    # Informational (P3/P4)
    ("mh073","Your account statement is ready","Your monthly account statement for September 2026 is ready. Sign in to view your statement and recent transactions.","P4","False","informational"),
    ("mh074","Project Kite: Meeting notes - Oct 1","Please find attached the meeting notes from today's Project Kite standup. Action items are listed in the document.","P3","False","informational"),
    ("mh075","Welcome to the team! Getting started guide","Welcome to MailMind! We are excited to have you on board. Here are resources to help you get started.","P4","False","informational"),
    ("mh076","Survey: Share your feedback on our product","We would love to hear your thoughts on our product. The survey takes approximately 5 minutes.","P4","False","informational"),
    ("mh077","Your privacy settings have been updated","We have updated our privacy policy. Your current settings remain unchanged.","P4","False","informational"),
    ("mh078","Team offsite: Save the date for November 15","Please save the date for our Q4 team offsite on November 15. More details to follow.","P3","False","informational"),
    ("mh079","Your profile was viewed 24 times this week","Your LinkedIn profile was viewed 24 times this week. Discover networking opportunities.","P4","False","informational"),
    ("mh080","Webinar recording available: AI in Healthcare","The recording from Tuesday's webinar on AI in healthcare is now available. Watch at your convenience.","P4","False","informational"),
    # Additional OTP / auth
    ("mh081","PhonePe: OTP for your transaction","Your PhonePe OTP is 448291. Valid for 10 minutes. Never share your OTP with anyone.","P1","True","otp_auth"),
    ("mh082","HDFC Bank: OTP for net banking","Your HDFC net banking OTP is 334412. This OTP is valid for 5 minutes. Do not share this OTP.","P1","True","otp_auth"),
    ("mh083","Paytm: OTP for payment","Your Paytm OTP is 221938. Valid for 10 minutes. Do not share with anyone.","P1","True","otp_auth"),
    ("mh084","Your login code for the admin dashboard","Use code 849201 to log in to the admin dashboard. This code expires in 5 minutes.","P1","True","otp_auth"),
    ("mh085","WhatsApp: Verification code","Your WhatsApp verification code is 491-082. You may also tap this link to verify your phone.","P1","True","otp_auth"),
    # Additional negative security
    ("mh086","Quarterly security compliance report","Your quarterly security compliance report is attached. All systems met required benchmarks for Q3 2026.","P4","False","security_info"),
    ("mh087","Your login was verified","Your login from Bangalore, India was verified. If this was not you, please secure your account.","P3","False","security_info"),
    ("mh088","Password changed successfully","Your account password has been successfully changed. If you made this change, no further action is required.","P4","False","security_info"),
    # Additional payments
    ("mh089","Refund processed: Rs 2499","Your refund of Rs 2499 has been processed and will reflect in your account within 5-7 business days.","P4","False","payments"),
    ("mh090","Receipt: Your order #84921","Thank you for your purchase. Your receipt for order #84921 is attached for your records.","P4","False","payments"),
    # Additional deadlines
    ("mh091","Passport renewal: Expires in 30 days","Your passport expires in 30 days. Apply for renewal now to avoid travel disruptions.","P2","True","deadlines"),
    ("mh092","Domain expiry reminder: 7 days","Your domain example.com expires in 7 days. Renew now to prevent service disruption.","P2","True","deadlines"),
    # Additional recruitment
    ("mh093","Application status update","Your application status has been updated to In Review. You will be contacted regarding next steps within 5 business days.","P3","False","recruitment"),
    ("mh094","Regret: Your application was not selected","Thank you for applying. We have decided to move forward with other candidates for this role.","P4","False","recruitment"),
    # Additional academic
    ("mh095","Scholarship deadline: October 15","Applications for the National Merit Scholarship are due October 15. Submit your application by 5 PM.","P1","True","academic"),
    ("mh096","Attendance shortage warning","Your attendance in CS471 has fallen below 75%. You must attend remaining classes to be eligible for the final exam.","P2","True","academic"),
    # Additional SaaS
    ("mh097","Critical: SSL certificate expires in 3 days","Your SSL certificate for api.yourapp.com expires in 3 days. Renew immediately to prevent HTTPS errors.","P1","True","saas"),
    ("mh098","Deployment failed: Production environment","Your deployment to production failed at step 3/5. Review the error logs and re-trigger the deployment pipeline.","P1","True","saas"),
    ("mh099","Weekly usage report: September 2026","Your weekly usage summary for September 2026 is attached. Review API calls, storage, and bandwidth.","P4","False","saas"),
    ("mh100","Changelog: Version 3.4.1 released","We released version 3.4.1 with bug fixes and performance improvements. Review the full changelog.","P4","False","saas"),
]

out_path = Path("dataset/processed/modern_email_holdout_v2.csv")
out_path.parent.mkdir(parents=True, exist_ok=True)
with open(out_path, "w", newline="", encoding="utf-8") as f:
    writer = csv.writer(f)
    writer.writerow(["holdout_id","subject","body","final_label","expected_action","topic"])
    writer.writerows(HOLDOUT_ROWS)
print(f"Written {len(HOLDOUT_ROWS)} rows to {out_path}")

from collections import Counter
cats = Counter(r[5] for r in HOLDOUT_ROWS)
labels = Counter(r[3] for r in HOLDOUT_ROWS)
print("\nCategory distribution:")
for cat, cnt in sorted(cats.items()):
    print(f"  {cat}: {cnt}")
print("\nLabel distribution:")
for lbl, cnt in sorted(labels.items()):
    print(f"  {lbl}: {cnt}")
