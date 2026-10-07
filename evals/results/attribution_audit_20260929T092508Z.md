# Attribution audit of stored memories

Judge gemini-2.5-pro, one call per scope over the full source history. raw is verbatim and not audited. Flagged memories are listed with the judge's evidence for hand review.

| customer | path | memories | flagged | STORED_MISSTATEMENT | OTHER_PERSON | HYPOTHETICAL_AS_FACT | WRONG_SPEAKER | MEMORY_ERROR | unjudged |
|---|---|---|---|---|---|---|---|---|---|
| 009 | managed | 14 | 2 | 1 | 0 | 0 | 0 | 2 | 0 |
| 009 | roles | 15 | 5 | 2 | 1 | 0 | 0 | 3 | 0 |
| 016 | managed | 17 | 2 | 0 | 0 | 0 | 0 | 2 | 0 |
| 016 | roles | 14 | 4 | 2 | 0 | 0 | 0 | 2 | 0 |
| 017 | managed | 13 | 2 | 1 | 0 | 0 | 0 | 1 | 0 |
| 017 | roles | 11 | 2 | 1 | 0 | 0 | 0 | 1 | 0 |
| 028 | managed | 10 | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| 028 | roles | 18 | 6 | 0 | 0 | 0 | 0 | 6 | 0 |
| 033 | managed | 13 | 1 | 1 | 0 | 0 | 0 | 1 | 0 |
| 033 | roles | 13 | 3 | 2 | 0 | 0 | 1 | 0 | 0 |
| **all** | **roles** | 71 | 20 | 7 | 1 | 0 | 1 | 12 | 0 |
| **all** | **managed** | 67 | 8 | 4 | 0 | 0 | 0 | 6 | 0 |

## Flagged memories

- **009 managed [2] MEMORY_ERROR** (said by nobody): I work in an office and enjoy camping and outdoor activities, but I do not enjoy hot, humid weather or outdoor sports like mountain climbing.  
  wrong: "do not enjoy... outdoor sports like mountain climbing"; source C01: "It's not like I'm a professional mountain climber or anything."; The customer stated he is not a professional mountain climber to make a point, but never said he dislikes or does not enjoy the sport. The memory invents this preference.
- **009 managed [11] STORED_MISSTATEMENT** (said by customer): I requested and escalated a written summary for a hotel charge dispute that I filed in April 2026.  
  wrong: "a hotel charge dispute"; source C08: "I'm actually still waiting on a written summary of that dispute I filed. The one about the hotel charge."; The customer mistakenly referred to the dispute as being for a 'hotel charge' in a chat, but all records show the merchant was 'Pinecrest Outdoor Supply'.
- **009 managed [11] MEMORY_ERROR** (said by nobody): I requested and escalated a written summary for a hotel charge dispute that I filed in April 2026.  
  wrong: "that I filed in April 2026"; source C04: "> On March 9, 2026, at 4:15 PM, Card Services <support@bank.example> wrote: > ... This message confirms that following your call today, we have opened dispute case DSP-7530420"; The dispute was filed on March 9, 2026. No one in the source states it was filed in April. The memory likely misinterpreted an agent's comment about 'case notes from April' as the filing date.
- **009 roles [0] OTHER_PERSON** (said by customer): The customer, Marcus, was born in Savannah and currently resides in Atlanta, Georgia. He works in an office, has a partner named Jordan, and has a wife who occasionally uses his card for shopping at Ross Dress for Less. He has family in Finland whom he plans to visit during an upcoming trip that also includes work travel.  
  wrong: "and has a wife who occasionally uses his card for shopping at Ross Dress for Less"; source C04: "My partner Jordan was laughing at me about it."; The customer consistently refers to his partner, Jordan, throughout the history. He only mentions a "wife" once, in passing, while guessing about a fraudulent charge. The memory presents the existence of both a partner and a wife as a fact, which is not substantiated and likely creates a non-existent person.
- **009 roles [1] MEMORY_ERROR** (said by nobody): On 2026-03-27 (secure chat, agent Priya), the customer's primary email address was updated from marcusl31@example.net to marcus.lindqvist50@example.net (after correcting an initial typo of marcuslindqvist50@example.net), which he verified again on 2026-04-06. On 2026-04-06 (phone call, agents Maria and Wes), he clarified that the phone number ending in 2900 on file is not his and designated his office landline 412-555-0147 as the best callback number, noting it is not the old fax line 412-555-0144. On 2026-04-29, the bank confirmed his email address and callback number 412-555-0147 on file. On 2026-07-28, the customer's primary callback number on file was updated from the old work landline 412-555-0147 to the new work number 412-555-0276, and he confirmed his email address on file is marcus.lindqvist50@example.net. On 2026-08-02 (confirmed complete on 2026-08-16 under case CASE-1447259), the customer's primary email address was updated from marcus.lindqvist50@example.net to lindqvist.m91@example.org, verified via an SMS OTP sent to the phone number on file 412-555-0276. On 2026-09-16, the customer confirmed their phone number on file starts with 412 and ends in 0276, and their current email on file starts with lindqvist.m91.  
  wrong: "confirmed complete on 2026-08-16 under case CASE-1447259"; source C10: "Date: 2026-08-02 10:35 AM ... This email serves as confirmation that the changes you requested have been successfully completed."; The email change was confirmed complete on August 2, 2026, not August 16. The case number CASE-1447259 is from a previous, unrelated card activation call and was mistakenly included in an internal agent note; it is not the case number for the email change.
- **009 roles [3] STORED_MISSTATEMENT** (said by agent): On 2026-03-09, the Chase Freedom Flex card *5997 was deactivated immediately due to fraudulent activity, and a replacement card was ordered to be sent to the customer's address in Atlanta, Georgia within 3-5 business days. On 2026-06-05, the customer activated their new Chase Freedom Flex card ending in *1073 to replace their previous card ending in *5997, which had a malfunctioning chip; this activation automatically deactivated the old card and was verified via a one-time passcode sent to the email address on file.  
  wrong: "On 2026-03-09, the Chase Freedom Flex card *5997 was deactivated immediately due to fraudulent activity"; source C05: "[2026-05-17] Primary issue is his card, the Chase Freedom Flex ending in *5997. - Cx states the chip has stopped working consistently for about a week."; Agent Grace stated on 2026-03-09 that card *5997 would be deactivated immediately. However, the customer was still using the same card on 2026-05-17, when he visited a branch to report its chip had stopped working. The memory incorrectly states the agent's unfulfilled action as a fact.
- **009 roles [4] MEMORY_ERROR** (said by nobody): On 2026-03-09, the bank promised to issue a provisional credit of $392.88 to the customer's account within ten business days (by 2026-03-23) while dispute DSP-7530420 (under case CASE-1447259) is investigated; this provisional credit posted on 2026-04-04. The bank advised that the merchant has until 2026-07-07 to respond with evidence. The promised written summary of the hotel charge dispute was never received; after agent Tom tracked the mailing on 2026-06-05, agent Omar escalated the issue on 2026-06-29 to his supervisor and the disputes department to have the summary emailed to marcus.lindqvist50@example.net on the same day. On 2026-07-28, agent Dana apologized because a previously promised written summary of the dispute case from six weeks prior was never processed, and submitted a new request to mail a case summary letter to the customer's address in Atlanta, Georgia, within seven to ten business days (by August 6 to August 11, 2026).  
  wrong: "(under case CASE-1447259)"; source C04: "The reference number for your overall inquiry is CASE-4234533."; The case number associated with the dispute opened on 2026-03-09 is CASE-4234533. Case CASE-1447259 was for a separate card activation call on 2026-06-05.
- **009 roles [4] STORED_MISSTATEMENT** (said by customer): On 2026-03-09, the bank promised to issue a provisional credit of $392.88 to the customer's account within ten business days (by 2026-03-23) while dispute DSP-7530420 (under case CASE-1447259) is investigated; this provisional credit posted on 2026-04-04. The bank advised that the merchant has until 2026-07-07 to respond with evidence. The promised written summary of the hotel charge dispute was never received; after agent Tom tracked the mailing on 2026-06-05, agent Omar escalated the issue on 2026-06-29 to his supervisor and the disputes department to have the summary emailed to marcus.lindqvist50@example.net on the same day. On 2026-07-28, agent Dana apologized because a previously promised written summary of the dispute case from six weeks prior was never processed, and submitted a new request to mail a case summary letter to the customer's address in Atlanta, Georgia, within seven to ten business days (by August 6 to August 11, 2026).  
  wrong: "hotel charge dispute"; source C04: "The dispute is for a charge from Pinecrest Outdoor Supply in the amount of $392.88."; The customer misremembered the dispute as being for a 'hotel charge' during a chat on 2026-06-29. The memory repeats this error as fact, but the actual dispute was for a charge from 'Pinecrest Outdoor Supply'.
- **009 roles [11] MEMORY_ERROR** (said by nobody): On 2026-06-29 (secure chat, agent Omar), a travel notice was set on the Chase Freedom Flex card *1073 for Vancouver, Canada, from 2026-08-16 to 2026-08-28. However, on 2026-08-02 (confirmed complete on 2026-08-16), this travel notice was cancelled because the trip was postponed indefinitely.  
  wrong: "(confirmed complete on 2026-08-16)"; source C10: "Date: 2026-08-02 10:35 AM ... This email serves as confirmation that the changes you requested have been successfully completed. ... 2. The travel notice for Vancouver, Canada ... has been cancelled as requested."; The cancellation of the travel notice was requested and confirmed complete on August 2, 2026, not August 16, 2026.
- **016 managed [7] MEMORY_ERROR** (said by nobody): I have had credit line increase requests declined, with eligibility to re-request after July 11, 2026, and again after October 10, 2026 (where keeping the request under $4,000.00 will avoid manual underwriting).  
  wrong: "and again after October 10, 2026"; source C09: "You can actually re-request that after July 11, 2026, not the October date it says here. Just an FYI."; The memory incorrectly combines two dates for re-requesting a credit line increase. An agent in C09 corrected the earlier information from C03, stating the correct date was July 11, not October 10. The memory presents both as valid, separate dates.
- **016 managed [12] MEMORY_ERROR** (said by nobody): I placed travel notices on my Chase Slate Edge credit card ending in 6065 for a trip to Reykjavik, Iceland, in June 2026, but cancelled the scheduled trip from August 14 to August 20, 2026 due to a family matter.  
  wrong: "in June 2026"; source C08: "Right. It's August 14th to August 20th. This year, 2026."; The memory incorrectly states the trip to Iceland was scheduled for June 2026. The travel notice was placed in June, but the trip itself was scheduled for August 14-20, 2026.
- **016 roles [1] MEMORY_ERROR** (said by nobody): On 2026-03-04, the bank promised a provisional credit of $473.31 within ten business days (by 2026-03-18) for dispute DSP-1512689; this credit was eventually posted on 2026-04-09, and on 2026-07-22, the customer was informed that the dispute was resolved in her favor on 2026-07-21, making the temporary credit permanent. On 2026-06-07, Sofia confirmed she had received the paper statement she had requested in late April 2026 via her updated primary email address.  
  wrong: "On 2026-06-07, Sofia confirmed she had received the paper statement she had requested in late April 2026"; source C05: "I asked if she had received the paper statement she requested last month. She confirmed she did receive it."; The customer confirmed receiving the paper statement during her branch visit on May 20, 2026, not during a phone call on June 7, 2026.
- **016 roles [9] MEMORY_ERROR** (said by nobody): On 2026-06-07 (during a phone call under case CASE-1453067, which was closed as resolved), the customer Sofia's replacement Chase Slate Edge card ending in *6065 was activated, and her old damaged card ending in *2837 (which was physically damaged with a worn strip and a snapped corner) was permanently deactivated. This activation follows her branch visit on 2026-05-20 to request a replacement after the old card snapped. During the activation, an initial call dropped, but a supervisor successfully called Sofia back on her landline to finish the activation as promised, and agent Anjali advised her that her existing PIN automatically transfers to the new card. Case CASE-1453067 also recorded her feedback that old email addresses are still showing in the quoted text of email threads despite her primary email being updated in March.  
  wrong: "a supervisor successfully called Sofia back on her landline to finish the activation"; source C07: "Hi, Ms. Doyle. My name is Anjali. I was just speaking with you a few moments ago from Chase Card Services? I’m so sorry, it seems our call was disconnected."; The agent who called the customer back after the initial call dropped was named Anjali; she did not identify herself as a supervisor.
- **016 roles [12] STORED_MISSTATEMENT** (said by agent): On 2026-09-13, during a call with agent Tom (reference CASE-2368315), the customer was advised that their statement closing date is the 15th of every month, with the payment due date always falling on the 10th of the following month.  
  wrong: "their statement closing date is the 15th of every month, with the payment due date always falling on the 10th of the following month"; source note 2025-01-03: "MONTHLY STATEMENT: Statement closed for Chase Slate Edge (*2837) with a balance of $1,486.08. Minimum due $29.72 by 2025-01-28."; Agent Tom stated the closing date is the 15th and due date is the 10th, but multiple account statements in the source show different closing and due dates (e.g., statement closed Jan 3, due Jan 28).
- **016 roles [13] STORED_MISSTATEMENT** (said by agent): On 2026-09-13, agent Tom confirmed that a $200.00 targeted retention statement credit, accepted by the customer during a branch visit on 2026-08-31, has no spending requirement and will be applied within two statement cycles, likely appearing on the statement closing on 2026-09-15 or at the latest by 2026-10-15 (reference CASE-2368315).  
  wrong: "has no spending requirement"; source C11: "I also told her about a targeted promotion we have running right now for a $200.00 statement credit on her Chase Slate Edge card if she hits a certain spend threshold over the next quarter."; Agent Tom told the customer the $200 credit had no spending requirement, but the branch agent who made the offer noted that it required hitting a certain spend threshold.
- **017 managed [0] STORED_MISSTATEMENT** (said by customer): I disputed a charge of $602.64 from Harbor Lights Florist for wedding flowers posted on February 28, 2026, on my Chase Slate Edge card ending in 4628 (dispute number DSP-2174159, case number CASE-8894325). The dispute was resolved in my favor, making my temporary credit permanent, and I requested an itemized paper statement of the charge to be mailed to my Atlanta address for the March 2026 billing cycle.  
  wrong: "for wedding flowers"; source C01: "I have never, ever heard of that place. A florist? For six hundred bucks? No way. Absolutely not."; The memory states the dispute was over the quality of wedding flowers, based on the customer's statement in C09. However, in the original dispute call (C01), the customer claimed he had never heard of the merchant and did not make the charge at all, making it a fraud claim, not a service dispute.
- **017 managed [11] MEMORY_ERROR** (said by nobody): My wife and I postponed our planned trip to Mexico City, Mexico, from August 10 to August 17, 2026, because the work conference I was attending was postponed, and I cancelled the travel notice on my Chase Slate Edge card.  
  wrong: "My wife and I"; source C10: "Unfortunately, the work conference I was supposed to attend has been postponed indefinitely, so the trip is off."; The source indicates the customer was traveling alone to Mexico City for a work conference. The memory incorrectly states that his wife was also part of the postponed trip, but there is no mention of anyone else accompanying him in the source material.
- **017 roles [2] STORED_MISSTATEMENT** (said by customer): The customer's wife is named Elara, and she was the one who primarily dealt with the florist for their wedding.  
  wrong: "The customer's wife is named Elara"; source C07: "My husband, Gustavo, he’s always telling me to just use my debit card, but I like the points."; The memory states the customer has a wife named Elara, based on a single mention in C01. However, the customer repeatedly and clearly refers to his husband, Gustavo, in multiple other sources (C03, C04, C05, C06, C07), making the statement about a wife a misstatement.
- **017 roles [6] MEMORY_ERROR** (said by nobody): The customer, Andre, resides in Atlanta, Georgia, and is married to Gustavo, who helps with their taxes and financial records and has a separate bank account. As of 2026-04-11, Gustavo was waiting for a replacement card ending in *1675 with phone number 502-555-0860. Their marriage and Atlanta residency were confirmed again on 2026-09-13.  
  wrong: "Their marriage... were confirmed again on 2026-09-13."; source C12: "The transcript of the call on 2026-09-13 contains no mention of the customer's spouse."; The memory claims the customer's marriage was confirmed on 2026-09-13, but the source for that date (C12) does not mention the customer's spouse at all. This fact is invented by the memory system.
- **028 managed [9] STORED_MISSTATEMENT** (said by agent): My Amazon Prime Visa card statement closing date is the 2nd of each month.  
  wrong: "the 2nd of each month"; source note 2025-03-03: "STATEMENT CLOSED for Amazon Prime Visa (*3810) with a balance of $2,891.98."; The memory states the statement closing date is the 2nd of the month, based on an agent's statement in C12. However, system notes show the statement closing on other dates, such as the 3rd of the month in March 2025 and the 4th of the month in April 2026.
- **028 roles [2] MEMORY_ERROR** (said by nobody): On 2026-03-04, agent Rafael advised that a provisional credit of $313.89 would post to the customer's account within ten business days, which posted on 2026-04-10. Dispute DSP-1480747 was closed in the customer's favor on 2026-07-24, making the $313.89 provisional credit on the Amazon Prime card *1337 permanent because the merchant failed to contest it by the final deadline.  
  wrong: "on the Amazon Prime card *1337"; source C09: "the provisional credit for $313.89 that was applied to your account is now permanent."; The source states the credit was applied to the customer's account. The memory incorrectly specifies it was on card *1337. The original charge was on card *3810, and credits are applied to the account, not a specific card number.
- **028 roles [4] MEMORY_ERROR** (said by nobody): Dispute DSP-1480747 (under case CASE-6327908) was opened on 2026-03-04 for an unrecognized charge of $313.89 from Harbor Lights Florist on the customer's Amazon Prime Visa card *3810, and was closed in her favor on 2026-07-24, making the credit on card *1337 permanent. Previously, as of 2026-04-12, the dispute had remained open, leading to follow-up case CASE-5599947 and complaints about a missing supervisor callback, which agents Dana and Grace addressed in June 2026.  
  wrong: "making the credit on card *1337 permanent"; source C09: "the provisional credit for $313.89 that was applied to your account is now permanent."; The source states the credit was applied to the customer's account. The memory incorrectly specifies it was on card *1337. The original charge was on card *3810, and credits are applied to the account, not a specific card number.
- **028 roles [5] MEMORY_ERROR** (said by nobody): On 2026-03-26, the customer's primary email was changed to nadia.park51@example.org, and the old email (nadiap30@example.com) was successfully purged by 2026-06-26. Following an update request on 2026-08-12, the customer confirmed on 2026-09-13 (call CASE-9931971) that her primary email address is park.n56@example.org.  
  wrong: "on 2026-08-12"; source C10: "On Mon, 27 Jul 2026 11:18:42 -0500, Nadia Park <nadia.park51@example.org> wrote:"; The memory states the customer requested an email update on August 12, 2026. The source email shows the request was sent on July 27, 2026.
- **028 roles [10] MEMORY_ERROR** (said by nobody): The customer prefers to have paper copies of their statements for their files, even though they have the mobile app. On 2026-04-29, the bank promised to mail a paper copy of the March 2026 statement for the Amazon Prime Visa *3810. Although the mailing was initially not received and the customer declined an offer to resubmit on 2026-06-03, she confirmed on 2026-07-24 that she had finally received the promised itemized paper statement.  
  wrong: "On 2026-04-29"; source C04: "On Apr 27, 2026, at 9:30 AM, Card Services <support@bank.example> wrote:"; The memory states the bank promised to mail a statement on April 29, 2026, but the source email shows the promise was made on April 27, 2026.
- **028 roles [11] MEMORY_ERROR** (said by nobody): On 2026-04-29, agent Marcus waived a $32.00 late fee on the customer's Amazon Prime Visa *3810 as a one-time courtesy and advised that such a waiver is only permitted once every 12 months; however, on 2026-07-24, agent Luis corrected this, clarifying that late fee courtesy waivers are actually only allowed once every 24 months.  
  wrong: "On 2026-04-29"; source C04: "On Apr 27, 2026, at 9:30 AM, Card Services <support@bank.example> wrote:"; The memory states the late fee was waived on April 29, 2026, but the source email from agent Marcus is dated April 27, 2026.
- **028 roles [12] MEMORY_ERROR** (said by nobody): On 2026-06-26 (secure chat with agent Tom), a travel notice was placed on the customer's Amazon Prime Visa card *1337 for travel to Dublin, Ireland, from 2026-08-07 to 2026-08-15; the customer noted it is a direct flight from Austin, TX. On 2026-08-12, during a secure message with agent Omar, the customer requested to cancel this travel notice, which was processed after verification because she had to postpone her planned trip to Ireland.  
  wrong: "On 2026-08-12"; source C10: "On Mon, 27 Jul 2026 11:18:42 -0500, Nadia Park <nadia.park51@example.org> wrote:"; The memory states the customer requested to cancel her travel notice on August 12, 2026. The source email shows the request was sent on July 27, 2026.
- **033 managed [0] STORED_MISSTATEMENT** (said by customer): I initiated a billing dispute (Dispute number: DSP-5976147, Case number: CASE-1603624) on March 6, 2026, for an unrecognized charge of $217.76 from Summit Ridge Ski Rentals on my Amazon Prime Visa ending in 6824. The dispute was successfully resolved and closed in my favor, making the provisional credit of $217.76 (posted on April 7, 2026) permanent. I requested an urgent supervisor callback (CASE-5177007) scheduled to occur on my office landline by April 10, 2026, but later filed a formal complaint (CASE-9083559) concerning a missed callback. I also had an expedited request submitted to mail a physical, paper copy of my March 2026 statement to my San Diego, CA address to assist with record-keeping.  
  wrong: "posted on April 7, 2026"; source C02: "I can confirm that a temporary credit for the charge was applied to your account earlier this month while we investigate."; The customer stated in a call on April 9 that the credit posted on April 7, but an agent on March 27 confirmed the credit had already been applied 'earlier this month' (i.e., in March). The memory repeats the customer's incorrect date as fact.
- **033 managed [0] MEMORY_ERROR** (said by nobody): I initiated a billing dispute (Dispute number: DSP-5976147, Case number: CASE-1603624) on March 6, 2026, for an unrecognized charge of $217.76 from Summit Ridge Ski Rentals on my Amazon Prime Visa ending in 6824. The dispute was successfully resolved and closed in my favor, making the provisional credit of $217.76 (posted on April 7, 2026) permanent. I requested an urgent supervisor callback (CASE-5177007) scheduled to occur on my office landline by April 10, 2026, but later filed a formal complaint (CASE-9083559) concerning a missed callback. I also had an expedited request submitted to mail a physical, paper copy of my March 2026 statement to my San Diego, CA address to assist with record-keeping.  
  wrong: "by April 10, 2026"; source C03, C06: "AGENT: I will have a supervisor call you back on that landline by Friday... CUSTOMER: The agent I spoke with promised one would call me back at my office number within forty-eight hours."; On a call on Wednesday, April 9, an agent promised a callback 'by Friday' and the customer later recalled this as 'within forty-eight hours'. Both point to Friday, April 11. The date 'April 10' is not mentioned in the source and is an error.
- **033 roles [2] WRONG_SPEAKER** (said by customer): On 2026-03-06, agent Grace advised the customer that her Amazon Prime Visa card *6824 includes travel and emergency assistance and baggage delay insurance, but full trip cancellation or interruption insurance is typically only on premium travel cards.  
  wrong: "agent Grace advised the customer"; source C01: "AGENT: Actually, while I have you, this is totally unrelated, but does this card have any kind of travel insurance? ... CUSTOMER: That's a great question. Let me just pull up the benefits guide for your specific card... yes, it looks like your Amazon Prime Visa does come with some travel and emergency assistance services, and a baggage delay insurance."; The memory states that agent Grace advised the customer about travel insurance benefits. However, the transcript shows the agent asked the question and the customer provided the detailed information about the card's benefits.
- **033 roles [8] STORED_MISSTATEMENT** (said by agent): On 2026-04-30, the bank processed a request (Job ID M-9834-260430) to mail a copy of the itemized March 2026 statement for the Amazon Prime Visa *6824 to the customer's address on file in San Diego, CA 92101. Although she did not receive the initial mailing because it was sent to an outdated secondary email address, phone agent Tom expedited a resubmission on 2026-06-07. On 2026-07-21, the customer confirmed that the resubmitted statement copy had successfully arrived in the mail as expected.  
  wrong: "because it was sent to an outdated secondary email address"; source C08: "Agent (Wes): That is very likely the reason, and I'm sorry for the frustration it caused."; The memory states as fact that a mailed statement copy was not received due to a wrong email address. This is illogical for a physical mailing, and the source only contains speculation from an agent that this was the reason, not a confirmed fact.
- **033 roles [12] STORED_MISSTATEMENT** (said by agent): On 2026-09-17, the customer called regarding statement dates and a promotional credit (documented under reference number CASE-1684194), verifying her identity using a code sent to her work landline on file. During this call, agent Luis explained that her Amazon Prime Visa statement closing date is the 22nd of each month, with payments due on the 16th or 17th of the following month, and clarified that the $200.00 statement credit promotion discussed by a banker during her branch visit on 2026-08-31 was an acquisition offer for new cardmembers and could not be applied to her existing account.  
  wrong: "clarified that the $200.00 statement credit promotion discussed by a banker during her branch visit on 2026-08-31 was an acquisition offer for new cardmembers and could not be applied to her existing account"; source C11: "I said something like, 'For example, just as an FYI, we're running a promotion right now where you could get a $200.00 statement credit just for setting up a new qualifying direct deposit.'"; The memory claims agent Luis clarified the promotion mentioned by the banker. However, the banker mentioned a $200 credit for setting up a direct deposit (C11), while agent Luis described a different promotion for new cardmembers based on spending (C12). The agent misidentified the promotion, and the memory reports this error as a factual clarification.

## Hand review 2026-09-29

Role-fed notes (run 242f33, `conversations_roles_20260929T053216Z.json`): turns sent with user / model roles, assistant
turns as context. Paths audited: `roles` (experiment 3 engine, custom topics) and `managed` (default engine). `commit` left
out. Every flag above was read against the conversation it cites; the passed memories were also searched for the four
misses known from the old notes (hotel-charge merchant, paper statement received, Cartagena trip taken, dispute moved to
the replacement card) and for the other old confirmed errors. Numbers count memories with at least one confirmed error.
Class: CUSTOMER = a customer's misstatement, guess or belief stored as fact; AGENT = an agent's statement stored as fact;
MB = Memory Bank's own error.

### Flags, one by one

- 009 managed [2] "does not enjoy outdoor sports like mountain climbing": REJECTED. Self-description / preference
  paraphrase ("It's not like I'm a professional mountain climber", "my big outdoor activity is walking to my car"); the
  label set excludes self-description.
- 009 managed [11] "hotel charge dispute": CONFIRMED, CUSTOMER. C08 customer: "The one about the hotel charge."; the
  dispute is Pinecrest Outdoor Supply (C01, C04). Secondary: "that I filed in April 2026" is a garble (filed 2026-03-09;
  the written-summary request was April; agent Tom in C07 said "back in April?"). One class per memory: CUSTOMER.
- 009 roles [0] "has a partner named Jordan, and has a wife": REJECTED, dataset inconsistency. C01 has "my wife sometimes
  goes there" and "I'm the only user on the account"; from C03 on it is "partner Jordan", an authorised user with card
  *4676. The memory keeps both; the source never resolves it.
- 009 roles [1] "confirmed complete on 2026-08-16 under case CASE-1447259": REJECTED. The C10 conversation is stamped
  2026-08-16 in the dataset (the emails inside are dated 08-02), and Keisha's internal note in C10 says
  "Ref CASE-1447259". Both come from the source.
- 009 roles [3] "*5997 was deactivated immediately on 2026-03-09": REJECTED, dataset inconsistency (agent Grace says so
  in C01; the card is still in use in May). Already noted in the 2026-09-26 review.
- 009 roles [4] "hotel charge dispute", "from six weeks prior": CONFIRMED, CUSTOMER. C08 customer "The one about the hotel
  charge"; C09 customer "maybe... six weeks ago?" for a promise made 2026-04-26 (13 weeks). Secondary MB error in the same
  memory: the 03-09 provisional-credit promise is put "under case CASE-1447259", which is the June activation case
  (the dispute case is CASE-4234533). Counted once, as CUSTOMER.
- 009 roles [11] "confirmed complete on 2026-08-16": REJECTED, conversation timestamp (see roles [1]).
- 016 managed [7] "after July 11, 2026, and again after October 10, 2026": REJECTED. Agent advice a later agent
  corrected; the note keeps both dates rather than the superseded one only. Clumsy merge, not an error.
- 016 managed [12] "trip to Reykjavik, Iceland, in June 2026": REJECTED, ambiguous phrasing (the notice was placed in
  June for an August trip); the August dates are in the same sentence.
- 016 roles [1] "On 2026-06-07, Sofia confirmed she had received the paper statement": REJECTED. She did say it on
  06-07 (C07: "I think it was. Yes. It came.") and on 05-20 (C05 "She confirmed she did receive it"); the judge missed
  C07. "requested ... via her updated primary email address" is true (C04). Note for the old audit's #5: the statement
  that "never arrived" in C09 is the May statement, a different request; the March one was received per C05 and C07.
- 016 roles [9] "a supervisor successfully called Sofia back on her landline to finish the activation as promised":
  CONFIRMED, CUSTOMER. C07 shows agent Anjali (not a supervisor) called back after the drop; the supervisor callback was
  the April dispute follow-up (C06). But the conflation is the customer's own, C08 (secure chat, customer turn): "That
  last call I made about the card activation just dropped completely. I did appreciate that the supervisor called me
  back on my landline like they promised". The old audit classed the same error MB (#6, #16); under the role feed the
  source of the sentence is a user turn, so it is reclassified CUSTOMER here. "as promised" is the merge residue.
- 016 roles [12] closing date 15th / due 10th: REJECTED. Agent Tom's statement reported as his; the routine statement
  notes that contradict it are generator noise (dataset).
- 016 roles [13] "agent Tom confirmed that a $200.00 targeted retention statement credit ... has no spending
  requirement": CONFIRMED, AGENT. Branch note C11 (2026-08-31): "a $200.00 statement credit on her Chase Slate Edge card
  if she hits a certain spend threshold over the next quarter". C12 model-role turn (agent Tom): "this was just a 'thank
  you for your business' offer, no spending requirement attached." The note states Tom's version as a confirmation.
  Same pattern as 033 roles [12], which the old audit confirmed (#13); treated the same way.
- 017 managed [0] "for wedding flowers": REJECTED, dataset inconsistency. C01 is a fraud claim ("never heard of that
  place"); C09 the customer says "flowers. For a wedding ... They delivered the wrong flowers" and C09/C11 his wife dealt
  with the florist. The note reports the customer's later version.
- 017 managed [11] "My wife and I postponed our planned trip": REJECTED, unverifiable (the source never says who was
  travelling).
- 017 roles [2] "wife is named Elara": REJECTED, dataset inconsistency (Elara in C01 and C09, husband Gustavo in C03-C07,
  C11). Noted in the 2026-09-26 review.
- 017 roles [6] "marriage ... confirmed again on 2026-09-13": REJECTED. C12: "My wife and I spend a lot on groceries."
  The judge missed it.
- 028 managed [9] closing date 2nd: REJECTED, routine notes are generator noise (as 016 roles [12]).
- 028 roles [2] "making the $313.89 provisional credit on the Amazon Prime card *1337 permanent": CONFIRMED, MB. The
  charge and dispute were on *3810 (C01); *1337 is the June replacement. Nobody in C09 puts the credit on *1337 (Luis
  only verifies "the primary card on the account, the one you're using now"). Same error as the old #10.
- 028 roles [4] "making the credit on card *1337 permanent": CONFIRMED, MB. Same error, second memory.
- 028 roles [5] "update request on 2026-08-12", [10] "On 2026-04-29", [11] "On 2026-04-29", [12] "On 2026-08-12":
  REJECTED, all four. These are the conversation timestamps in the dataset (C04 is stamped 04-29, C10 is stamped 08-12);
  the emails inside carry earlier dates. Missing / approximate date rule.
- 033 managed [0] "posted on April 7, 2026": REJECTED. C03 (2026-04-09): "It showed up ... the day before yesterday",
  agent confirms. C02 (03-27, agent Anjali) says a temporary credit was applied "earlier this month": the two
  conversations contradict each other (dataset inconsistency, new). "by April 10, 2026": REJECTED, 2026-04-09 is a
  Thursday and Omar promised "by Friday".
- 033 roles [2] WRONG_SPEAKER (Grace advised on travel insurance): REJECTED. The C01 transcript has the AGENT / CUSTOMER
  labels swapped for that exchange (the "customer" reads the benefits guide); the memory attributes by content. Dataset
  artefact.
- 033 roles [8] "not received because it was sent to an outdated secondary email address": REJECTED, per the 2026-09-26
  correction: agent Wes in C08 says "That is very likely the reason". (The sentence is garbled: a mailing "sent to an
  email address".)
- 033 roles [12] "agent Luis ... clarified that the $200.00 statement credit promotion discussed by a banker during her
  branch visit on 2026-08-31 was an acquisition offer for new cardmembers": CONFIRMED, AGENT. Branch note C11: "a
  $200.00 statement credit just for setting up a new qualifying direct deposit". C12 model-role turn (agent Luis): "It
  looks like this was an offer for... for new cardmembers, for the Amazon Prime Visa card. It was a credit that you
  would receive after spending a certain amount in the first three months". Customer turn echoes it: "So... I can't get
  it." Same as the old #13.

### Found in the passed memories (judge misses)

- 028 roles [0] "a dropped call occurred during the activation of the replacement card *1337 ... but the card was
  successfully activated on a callback": CONFIRMED, CUSTOMER. C07: the customer called back in ("we got cut off"; Grace:
  "I was literally in the middle of dialing your callback number this very second when your call came through"). The
  "callback" is her own later version: C08 "someone called me back eventually", C10 "the person who called me back was
  very helpful". Same as the old #19.
- 033 roles [4] "updated on 2026-08-15 to okafor.i49@example.com ... (verified via secure message with agent Rafael with
  a code sent to her number 912-555-0100)": CONFIRMED, MB (borderline, as the old #12 / #23). C10: Rafael offers an SMS
  code, the customer says "now is a fine time to send the code"; the confirmation says verified by "Name, DOB
  [REDACTED], etc." and never mentions a code. An offered step recorded as done. Kept for consistency with the old audit.
- Not present in any roles or managed note: "traveled to Cartagena" (033 roles [11] and managed [9] both say cancelled);
  the 033 dispute on *9995 (roles [1] and managed [0] say *6824); the 028 email "two attempts because the first agent
  recorded it incorrectly"; the 028 "dispute resolved" belief of 05-16; 016 "resolved" on 06-07; 009 "July 2026"
  charge; 017 "May 2026" charge (roles [0] and managed [0] both say 2026-02-28).
- Near miss, not counted: 033 managed [11] "I inquired about a $200 statement credit promotion ... but was informed it is
  only available to new cardmembers" reports what she was told (customer turn: "So... I can't get it") without endorsing
  it. Luis's wrong conclusion reaches the managed note through the customer's echo. 033 managed [3] "to resolve an issue
  with missing electronic statements" is a paraphrase drift (the missing item was a mailed statement copy), not counted.

### Totals

| path | memories | judge flags (memories) | confirmed | CUSTOMER | AGENT | MB |
|---|---|---|---|---|---|---|
| roles | 71 | 20 (18) | 8 | 3 | 2 | 3 |
| managed | 67 | 8 (8) | 1 | 1 | 0 | 0 |
| **both paths** | 138 | 28 (26) | 9 | 4 | 2 | 3 |

Old feed, for comparison (audit of 2026-09-25, corrected 09-26): 23 of 363 (extract 13/274, both 10/89): CUSTOMER 11,
AGENT 2, MB 10. Per customer the old notes carried about 2-3 confirmed errors on each of two paths; the role-fed notes
carry 0-3 on roles (009: 1, 016: 2, 017: 0, 028: 3, 033: 2) and 0-1 on managed (009 only).

Confirmed, roles: 009[4] CUSTOMER; 016[9] CUSTOMER; 016[13] AGENT; 028[0] CUSTOMER; 028[2] MB; 028[4] MB; 033[4] MB;
033[12] AGENT. Confirmed, managed: 009[11] CUSTOMER.

What changed against the expectation in the handoff:
1. AGENT is not empty. Two roles notes state an agent's wrong claim as a confirmation / clarification, and both come from
   model-role turns (016 C12 Tom, 033 C12 Luis). The custom topic that records advice and commitments extracts the
   model turn; "assistant turns are context only" does not hold for that topic. The managed path has no AGENT error (its
   one near miss arrives through the customer's echo).
2. CUSTOMER persists, as expected: hotel charge (009, both paths), "six weeks" (009), "activated on a callback" (028),
   and 016's "the supervisor called me back" which the old audit had classed MB; under the role feed its source is a
   user turn.
3. MB persists but is smaller: the dispute on the replacement card (028 *1337, twice) and the offered code recorded as
   done (033). The 033 *9995 card, the Cartagena trip, the 016 double callback (now traced to the customer) and the
   009 letter channel are gone.

Dataset inconsistencies met this pass (generator, not Memory Bank): 009 wife vs partner Jordan and "only user" vs
authorised user; 009 *5997 "deactivated" in C01 but used in May; 016 husband Mark (C01) vs wife Renata; 017 wife Elara
vs husband Gustavo; 017 fraud claim (C01) vs wrong-flowers service dispute (C09); 028 three bank names (Premier
OmniBank, Premier Financial, Consolidated Trust); 033 C01 speaker labels swapped on the travel-insurance exchange; 033
provisional credit "earlier this month" (C02, 03-27) vs posted 04-07 (C03); 016 C11 branch "spend threshold" vs C12 "no
spending requirement" (this one is counted, as the record contradicts the later agent); routine statement notes
contradict every agent-stated closing date; conversation timestamps differ from the dates inside email threads (009 C10,
028 C04, C10).

Limits: one judge pass per scope, recall not measured (two confirmed errors were found only by targeted search of the
passed memories); 5 customers, synthetic conversations; the AGENT / CUSTOMER split of 016 roles [9] rests on one
customer sentence in C08.
