# word_list.py
# Bundled word list for browse/filter/random. Loaded from words.txt or built-in list.

from pathlib import Path

_WORDS_FILE = Path(__file__).resolve().parent / "words.txt"

# Fallback list if words.txt missing: common words A-Z, various lengths
_FALLBACK = """about above across after again all also always am an and animal another
answer any are around as ask at away back be because been before begin being below
best better between big bird black blue both boy bring build but buy by call came
can car carry cat change child children city close come could cut day did do does
dog done down draw drink each eat end even every example eye face family far
father find first fish follow food for form found four from full get girl give go
good got great green grow had hand hard has have he head hear help her here high
him his home house how idea if in into is it its jump just keep kind know land
last late leave left let letter life light line list little live long look made
make man many may me mean men might more most mother move much must my name need
never new next night no not now number of off old on one only open or other our
out over own part people place play point put read right run said same say see
sentence set she should show side small so some something sometimes sound spell
start state still story study such take talk tell than that the their them then
there these they thing think this those thought three through time to together
too two under use very want was way we well went were what when where which
while who will with word work world would write year you your
ability able accept according account achieve action activity actually add
address administration admit adult affect after again against age agency
agent agreement ahead air all allow almost alone along already also
although always american among amount analysis and animal another answer
any anyone anything appear apply approach area argue arm around arrive
art article artist as ask assume at attack attention attorney audience
author authority available avoid away baby back bad ball bank bar base
basis beat beautiful because become bed before begin behavior behind
belief believe benefit best better between beyond big bill billion
bird birth bit black blood blue board body book border born both box
boy break bring brother budget build building business but buy by
call camera camp campaign campus can cancer candidate capital car
card care career carry case catch cause cell center central century
certain certainly chair challenge chance change character charge check
child choice choose church citizen city civil claim class clear
clearly close coach cold collection college color come commercial
common community company compare computer concern condition
conference congress consider consumer contain continue control
cost could country couple course court cover create crime cultural
culture current customer cut dark data daughter day dead deal death
decade decide decision deep defense degree democrat democratic
describe design despite detail determine develop development die
difference different difficult dinner direction director discover
discuss discussion disease do doctor dog door down draw dream
drive drop drug during each early east easy eat economic economy
edge education effect effort eight either election else employee
end energy enjoy enough enter entire environment environmental
especially establish even evening event ever every everyone
everything evidence exactly example executive exist expectation
experience expert explain eye face fact factor fail failure fall
family far fast father fear federal feel feeling few field fight
figure fill film final finally financial find fine finger finish
fire firm first fish five floor fly focus follow food foot for
force foreign forget form former forward four free friend from
front full fund future game garden gas general generation get
girl give glass go goal good government great green ground group
grow growth guess gun guy hair half hand hang happen happy hard
have he head health hear heart heat heavy help her here herself
high him himself his history hit hold home hope hospital hot
hour house how however huge human hundred husband idea identify
if image imagine impact important improve in include including
increase indeed indicate individual industry information inside
instead institution interest interesting international interview
into investment involve issue it item its itself job join just
keep key kid kill kind kitchen know knowledge land language
large last late later laugh law lawyer lay lead leader learn
least leave left leg legal less let letter level lie life light
like likely line list listen little live local long look lose
loss lot love low machine magazine main maintain major majority
make man manage management manager many market marriage material
matter may maybe me mean measure media medical meet meeting
member memory mention message method middle might military
million mind minute miss mission model modern moment money
month more morning most mother mouth move movement movie mr
mrs much music must my myself name nation national natural
nature near nearly necessary need network never new news
newspaper next nice night nine no none nor north not note
nothing notice now number occur of off offer office officer
official often oh oil ok old on once one only onto open
operation opportunity option or order organization other others
our ourselves out outside over own owner page pain painting
pair parent part participant particular particularly partner
party pass past patient pattern pay peace people per perform
performance perhaps period person personal phone physical
picture piece place plan plant play player please plus pm
point police policy political politics poor popular population
position positive possible power practice prepare presence
present president pressure pretty prevent price private
probably problem process produce product production
professional professor program project property protect
prove provide public pull purpose push put quality question
quickly quite race radio raise range rate rather reach read
ready real reality realize really reason receive recent
recently recognize recommend record red reduce reflect
region relate relationship religious remain remember remove
report represent republican require research resource
respond response responsibility rest result return reveal
rich right rise risk road rock role room rule run safe same
save say scene school science scientist score sea season
seat second section security see seek seem sell send senior
sense series serious serve service set seven several sex
sexual shake share she sheet shift ship shoe shoot short
shot should shoulder show side sign significant similar
simple simply since sing single sister sit site situation
six size skill skin small smile so social society soldier
some somebody someone something sometimes son song soon
sort sound source south space speak special specific
speech spend sport spring staff stage stand standard star
start state statement station stay step still stock stop
store story strategy street strong structure student study
stuff style subject success successful such suddenly suffer
suggest summer support sure surface system table take talk
task tax teach teacher team technology television tell ten
tend term test than thank that the their them then theory
there these they thing think third this those though thought
thousand threat three through throughout throw thus time to
today together tonight too top total tough toward town trade
traditional training travel treat treatment tree trial trip
trouble true truth try turn tv two type under understand
unit until up upon us use usually value various very victim
view violence visit voice vote wait walk wall want war watch
water way we weapon wear week weight well west western what
whatever when where whether which while white who whole whom
whose why wide wife will win wind window wish with within
without woman wonder word work worker world worry would
write writer wrong yard yeah year yes yet you young your
yourself""".split()


def get_all_words():
    """Return full list of words (lowercase, no duplicates)."""
    if _WORDS_FILE.exists():
        try:
            text = _WORDS_FILE.read_text(encoding="utf-8")
            words = [w.strip().lower() for w in text.split() if w.strip().isalpha()]
            return sorted(set(words))
        except Exception:
            pass
    return sorted(set(_FALLBACK))


def filter_words(words, start_letter=None, min_len=None, max_len=None):
    """Filter word list by optional starting letter and length range."""
    out = words
    if start_letter and start_letter != "All":
        letter = (start_letter or "").strip().upper()
        if letter and len(letter) == 1:
            out = [w for w in out if w.startswith(letter.lower())]
    if min_len is not None and min_len > 0:
        out = [w for w in out if len(w) >= min_len]
    if max_len is not None and max_len > 0:
        out = [w for w in out if len(w) <= max_len]
    return out


def get_length_range_choices():
    """Return choices for length filter: (label, (min_len, max_len))."""
    return [
        ("Any length", (None, None)),
        ("3–4 letters", (3, 4)),
        ("5–6 letters", (5, 6)),
        ("7–8 letters", (7, 8)),
        ("9+ letters", (9, None)),
    ]
