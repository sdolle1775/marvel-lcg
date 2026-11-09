from core import *
from game.card import *
from game.ability import *
from cards.paper import Paper
from engine.lib import Json
from engine.log import Log
from engine.file import FileManager
from engine.file import Cache

from engine.config import ConfigVariables
from build import Build

CARDS_JSON_FILE         = ConfigVariables.File('cards_json_file', './data/cards.json')
CARDS_JSON_CUSTOM_FILE  = ConfigVariables.File('cards_json_custom_file', '')
CARDS_JSON_CUSTOM_FILES = ConfigVariables.Files('cards_json_custom_files', [])

class CardsDB:
    ability_link_cards: Dict[str, str] = {}
    full_link_cards: Dict[str, str] = {}

    sets_cards: Dict[str, List[str]] = {}

    # card_datas: Dict[str, List[Paper]] = {}
    papers: Dict[str, Paper] = {}
    linked_papers: Dict[str, List[str]] = {}

    ability_cache: Dict[str, List['Ability']] = {}

    cards_custom_files: List[str] = []
    cards_json_file = ""
    checksum_ok: bool = True

    @staticmethod
    def Initialize() -> None:
        cards_custom_file = [CARDS_JSON_CUSTOM_FILE.value] if CARDS_JSON_CUSTOM_FILE.value else []
        CardsDB.cards_custom_files = CARDS_JSON_CUSTOM_FILES.value + cards_custom_file
        CardsDB.cards_json_file = CARDS_JSON_FILE.value

        _, checksum_ok = Json.LoadInternal("./data/sets_info.json")
        CardsDB.checksum_ok &= checksum_ok == "Ok"

        def add_set(paper: 'Paper'):
            set_name = paper.set_name
            card_id = paper.card_id
            if set_name not in CardsDB.sets_cards:
                CardsDB.sets_cards[set_name] = []
            CardsDB.sets_cards[set_name].append(card_id)

        for json_name in CardsDB.cards_custom_files + [CardsDB.cards_json_file,]:
            if json_name == "":
                continue
            # check_sum = "Ignore" if json_name != CardsDB.cards_json_file else "Warn"
            card_origin_data, checksum_ok = Json.LoadInternal(json_name)
            if json_name == CardsDB.cards_json_file:
                CardsDB.checksum_ok &= checksum_ok == "Ok"
            for pack in card_origin_data:
                # CardsDB.card_datas[pack] = []
                for paper in card_origin_data[pack]:
                    full_link_id = Paper.GetFullLink(paper)
                    if full_link_id:
                        card_id = Paper.GetCardId(paper)
                        CardsDB.papers[card_id] = copy(CardsDB.papers[full_link_id])
                        CardsDB.papers[card_id].card_id = card_id
                        Cache.SetLinkPic(card_id, full_link_id)
                        CardsDB.full_link_cards[card_id] = full_link_id
                        add_set(CardsDB.papers[card_id])
                    else:
                        ability_link_id = Paper.GetAbilityLink(paper)
                        paper = Paper.Load(paper, pack)
                        if paper.card_id not in CardsDB.papers:
                            card_id = paper.card_id
                            if paper.card_id != "player":
                                assert card_id not in CardsDB.papers, f"{paper.card_id=}"

                            CardsDB.papers[paper.card_id] = paper
                            add_set(CardsDB.papers[paper.card_id])
                            # CardsDB.card_datas[pack].append(paper)
                            if ability_link_id:
                                CardsDB.ability_link_cards[card_id] = ability_link_id


        for card_id in CardsDB.papers:
            paper = CardsDB.papers[card_id]
            if 'Linked' not in paper.desc:
                continue
            linked_name = paper.desc['Linked']
            card_id = CardsDB.FindCardPaper(linked_name).card_id

            if card_id in CardsDB.linked_papers:
                CardsDB.linked_papers[card_id].append(paper.card_id)
            else:
                CardsDB.linked_papers[card_id] = [paper.card_id]


    @staticmethod
    def FindCardPaper(name_or_id: str) -> 'Paper':
        if name_or_id in CardsDB.papers:
            return CardsDB.papers[name_or_id]

        for card_id in CardsDB.papers:
            card_paper = CardsDB.papers[card_id]
            if card_paper.card_id == name_or_id or card_paper.name == name_or_id:
                return card_paper

        # for pack_name in CardsDB.card_datas:
        #     for card_paper in CardsDB.card_datas[pack_name]:
        #         if card_paper.card_id == name_or_id or card_paper.name == name_or_id:
        #             return card_paper

        # Log.Debug(name_or_id)
        assert False, f"{name_or_id=}"

    @staticmethod
    def FindAbilities(origin_card_id: 'str', pack: 'str', set_name: 'str') -> Sequence['Ability']:
        import importlib
        import importlib.util
        import ast
        import tokenize

        if origin_card_id in CardsDB.ability_cache:
            return CardsDB.ability_cache[origin_card_id]

        card_id = origin_card_id

        load_from_ability_link = False
        visited: Set[str] = set()
        # A copied face can itself delegate its abilities (for example the
        # Civil War Resistance setup faces). Follow the entire chain.
        while card_id in CardsDB.ability_link_cards or card_id in CardsDB.full_link_cards:
            assert card_id not in visited, f"Circular card ability link from {origin_card_id}: {card_id}"
            visited.add(card_id)
            if card_id in CardsDB.ability_link_cards:
                target_id = CardsDB.ability_link_cards[card_id]
                load_from_ability_link = True
            else:
                target_id = CardsDB.full_link_cards[card_id]
            paper = CardsDB.FindCardPaper(target_id)
            card_id = paper.card_id
            pack = paper.pack
            set_name = paper.set_name

        ability_module = None

        def has_unbuild_py() -> str|None:
            card_paths = [
                f"cards/{card_id}.py",
                f"cards/{card_id}.py.txt",
                f"cards/pack/{card_id}.py",
                f"cards/pack/{card_id}.py.txt",
            ]
            for path in card_paths:
                if FileManager.Exists(path):
                    return path
            return None

        unbuild_py = has_unbuild_py() if CardsDB.cards_custom_files else None

        if unbuild_py:

            def try_load_module_user_defined(card_id: str):
                try:
                    # Construct the full path to the module
                    full_path = unbuild_py
                    
                    # Follow Python's source encoding rules, including UTF-8
                    # BOMs and coding declarations, on every Windows locale.
                    with tokenize.open(full_path) as file:
                        file_content = file.read()
                    
                    # Parse the file content into an AST
                    tree = ast.parse(file_content, filename=full_path)
                    
                    # `from . import *` -> `from cards.pack import *`
                    class ImportTransformer(ast.NodeTransformer):
                        def visit_ImportFrom(self, node: ast.ImportFrom):
                            if node.module is None and node.names and node.names[0].name == '*':
                                node.module = 'cards.pack'
                                node.level = 0
                            return node

                    tree = ImportTransformer().visit(tree)
                    # Compile the modified AST
                    code = compile(tree, full_path, 'exec')
                    
                    # Create a new module and execute the compiled code in its context
                    spec = importlib.util.spec_from_loader(card_id, loader=None)
                    assert spec
                    ability_module = importlib.util.module_from_spec(spec)
                    exec(code, ability_module.__dict__)
                    
                    return ability_module
                except Exception as e:
                    raise RuntimeError(f"Error loading custom card {card_id} from {unbuild_py}: {e}") from e

            ability_module = try_load_module_user_defined(card_id)

        else: # if card_id not in CardsDB.ability_cache:
            set_name = FileManager.CleanName(set_name)

            module_paths = [f"cards.pack.{pack}.{card_id}"]
            if set_name:
                module_paths = [f"cards.pack.{pack}.{set_name}.{card_id}"] + module_paths

            if set_name.endswith("_nemesis"):
                path = f"cards.pack.{pack}.{set_name}"[0:-len("_nemesis")]
                module_paths.append(f'{path}.{card_id}')

            def try_load_module(module_path: str):
                try:
                    ability_module = importlib.import_module(module_path)
                    return ability_module
                except:
                    pass
                return None

            for module_path in module_paths:
                ability_module = try_load_module(module_path)
                if ability_module:
                    break

        if ability_module:
            try:
                abilities = ability_module.GetAbilities()
            except Exception as e:
                if unbuild_py:
                    raise RuntimeError(f"Error creating abilities for custom card {origin_card_id} from {unbuild_py}: {e}") from e
                raise
            CardsDB.ability_cache[origin_card_id] = abilities
            if not Build.release:
                paper = CardsDB.FindCardPaper(origin_card_id)
                if "TeamUp" in paper.desc:
                    for ability in CardsDB.ability_cache[origin_card_id]:
                        selectors = ability.selectors
                        assert selectors and selectors[0] and selectors[0].target_text == "TeamUp", f"{origin_card_id=}"
        else:
            CardsDB.ability_cache[origin_card_id] = []
            assert not load_from_ability_link, f"{origin_card_id=} {origin_card_id=}"

        return CardsDB.ability_cache[origin_card_id]

    @staticmethod
    def FindLikedPapers(find_paper: Paper) -> List[str]:
        if find_paper.card_id in CardsDB.linked_papers:
            return CardsDB.linked_papers[find_paper.card_id]
        return []

    @staticmethod
    def GetPapers(*,
                card_type: str|None=None,
                trait: str|None=None,
                card_class: str|None=None,
                card_classes: List[str]|None=None,
                set_name: str|None=None,
                check_fn: Callable[['Paper'], bool]|None=None,
                ) -> List[str]:
        def check(paper: Paper) -> bool:
            if card_type != None and paper.type != card_type:
                return False
            if card_classes != None:
                if "Class" not in paper.desc:
                    return False
                if paper.desc["Class"] not in card_classes:
                    return False
            if card_class != None:
                if "Class" not in paper.desc:
                    return False
                if paper.desc["Class"] != card_class:
                    return False
            if set_name != None:
                if paper.set_name != set_name:
                    return False
            if trait != None:
                if trait not in paper.traits:
                    return False
            if check_fn != None:
                if not check_fn(paper):
                    return False
            return True

        return [x for x in CardsDB.papers if check(CardsDB.papers[x])]

