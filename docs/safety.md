# Safety

SENTINEL-911 is a **research/educational** decision-support prototype.

## Hard rules

1. Never auto-dispatch real units.  
2. Never send real SMS or call 911 APIs.  
3. LLM never assigns urgency score.  
4. HAZMAT plans need warning + DEMO protocol citations.  
5. GREEN must not receive highest-priority unit sets.  
6. Low confidence / modality conflicts require human review.  
7. RED/YELLOW require dispatcher confirmation.  
8. Max 2 plan revisions; then abstain + escalate.  

## Privacy

- Raw audio logging off by default (`LOG_RAW_AUDIO=false`)  
- Basic PII redaction in logs  
- Secrets via environment variables only  

Production deployment would require legal, privacy, security, and emergency-services validation far beyond this MVP.
