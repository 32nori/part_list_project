from django.shortcuts import render
from django.views.generic.list import ListView
from django.db.models import Q
from part_list_app.models import Composition, Part, CompositionChangeSet, CompositionHistory, UndoRedoPointer
# from django.http import HttpRequest
from django.http import JsonResponse
from django.db.models import Max
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import reverse


class ProductList(ListView):
    context_object_name = 'compositions'
    template_name = 'part_list_app/composition_list.html'
    paginate_by = 5  # １ページは最大5件ずつでページングする

    # def get(self, request, *args, **kwargs):
    #     compositions = Composition.objects.filter(parent_id=None)
    #     self.object_list = compositions

    #     context = self.get_context_data(object_list=self.object_list)
    #     return self.render_to_response(context)

    def get_queryset(self):
        queryset = Composition.objects.filter(parent_id=None)

        query = self.request.GET.get('query')
        if query is not None and query != '':
            queryset = queryset.filter(
                Q(part__name__icontains=query) |
                Q(part__code__icontains=query)
            )
        
        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context['query'] = self.request.GET.get('query', '')  # queryをcontextに追加
        return context


def composition_edit(request, product_id=None):
    if product_id is None:
        nodes = None
        title = '構成を追加'
    else:
        # 実行
        nodes = find_by_product_id(product_id)
        title = '構成を変更'

    undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'part_list_app/composition_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status, 'title': title}
                  )


def get_children(id, quantity):
    compositions = Composition.objects.filter(parent_id=id).order_by('sort')
    children = []
    for composition in compositions:
        child = {
            'id': composition.id,
            'code': composition.part.code,
            'name': composition.part.name,
            'quantity': composition.quantity,
            'usedquantity': quantity * composition.quantity,
            'children': get_children(composition.id, quantity * composition.quantity)
        }
        children.append(child)
    return children


# 変更画面の削除処理
def composition_edit_del(request, product_id):
    current_composition_id = request.GET.get("current_composition_id")

    # エラーチェック
    if Composition.objects.filter(pk=current_composition_id).exists():
        exists = True
        # 実行
        with transaction.atomic():
            # product_idとcurrent_composition_idが同じ場合の処理をこちらにかく。
            # elseの場合、下のロジックが動くように改める。
            current_composition_id_int = int(current_composition_id)
            if product_id == current_composition_id_int:
                # 選択行のインスタンスを取得
                current_composition = Composition.objects.get(pk=current_composition_id)
                # 選択された行のidの子を取得する。
                children_data = delete_childrens(current_composition.id)
                # 取得された子のデータをフラットにしてならべる
                all_children = get_all_children(children_data)
                # 全ての子を削除する
                for child in all_children:
                    child_composition = Composition.objects.get(pk=child['id'])
                    child_composition.delete()
                current_composition.delete()
                return JsonResponse({"exists": exists})
            else:
                # undoRedoPointerの値よりCompositionChangeSet、CompositionHistoryの値を再更新する。
                update_history_from_pointer(product_id)
                # 新しい CompositionChangeSet インスタンスを作成
                composition = Composition.objects.get(id=product_id)
                composition_change_set = CompositionChangeSet.objects.create(product=composition)
                # 選択行のインスタンスを取得
                current_composition = Composition.objects.get(pk=current_composition_id)
                # 選択された行のidの子を取得する。
                children_data = delete_childrens(current_composition.id)
                # 取得された子のデータをフラットにしてならべる
                all_children = get_all_children(children_data)
                # 全ての子を削除する
                for child in all_children:
                    # Composition.objects.get(pk=child['id']).delete()
                    child_composition = Composition.objects.get(pk=child['id'])
                    # child_composition.delete()の実行後にHistoryに書き込むとpk(id)などの値がNoneとなってしまう
                    # 為、実行順序を1.Historyへの書き込み、2.child_composition.delete()の実行へ変えました。
                    CompositionHistory.objects.create(
                        composition_change_set=composition_change_set,
                        composition_original_id=child_composition.id,
                        parent_original_id=child_composition.parent_id,
                        sort=child_composition.sort,
                        part=child_composition.part,
                        quantity=child_composition.quantity,
                        action='delete',
                        status='before'
                    )
                    child_composition.delete()
                # current_composition.delete()の実行後にHistoryに書き込むとpk(id)などの値が
                # Noneとなってしまう為、実行順序を1.Historyへの書き込み、2.composition.delete()の
                # 実行へ変えました。
                CompositionHistory.objects.create(
                    composition_change_set=composition_change_set,
                    composition_original_id=current_composition.id,
                    parent_original_id=current_composition.parent_id,
                    sort=current_composition.sort,
                    part=current_composition.part,
                    quantity=current_composition.quantity,
                    action='delete',
                    status='before'
                )
                current_composition.delete()

                # 指定したproductのUndoRedoPointerオブジェクトを取得
                pointer, created = UndoRedoPointer.objects.get_or_create(
                    product=composition,
                    defaults={
                        'pointer': composition_change_set
                    }
                )
                # すでに存在する場合は、pointer_idを更新
                if not created:
                    pointer.pointer = composition_change_set
                    pointer.save()
                undo_status, redo_status = check_undo_redo(product_id)
                return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})
    else:
        exists = False
        return JsonResponse({"exists": exists})


# 削除対象のidを格納する。
def delete_childrens(id):
    child_compositions = Composition.objects.filter(parent_id=id)
    children = []
    for child_composition in child_compositions:
        child = {
            'id': child_composition.id,
            'part_id': child_composition.part_id,
            'children': delete_childrens(child_composition.id)
        }
        children.append(child)
    return children


# 階層構造リストをフラットにする。
def get_all_children(data):
    all_children = []

    for item in data:
        all_children.append(item)
        all_children.extend(get_all_children(item['children']))

    return all_children


# TODO 追加画面の製品挿入処理
def composition_add_product(request):
    edit_block_code = request.GET.get("edit_block_code")
    try:
        # エラーチェック
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない製品が指定されました。")

        # 実行
        with transaction.atomic():
            # 製品の登録
            # new_composition_instance = Composition()
            # edit_block_code を適切な PartMaster インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_composition_instance = Composition()
            new_composition_instance.parent_id = None
            new_composition_instance.sort = 1
            new_composition_instance.part = part_instance   # 正しい Part インスタンスを設定
            new_composition_instance.quantity = None
            new_composition_instance.save()

            composition_change_set = CompositionChangeSet.objects.create(product=new_composition_instance)

            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=new_composition_instance.id,
                parent_original_id=new_composition_instance.parent_id,
                sort=new_composition_instance.sort,
                part=new_composition_instance.part,
                quantity=new_composition_instance.quantity,
                action='create',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=new_composition_instance,
                defaults={
                    'pointer': composition_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = composition_change_set
                pointer.save()
    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})
    undo_status, redo_status = check_undo_redo(new_composition_instance.id)
    return JsonResponse({"success": True,
                         "new_id": new_composition_instance.id,
                         "name": part_instance.name, 'undo': undo_status,
                         "redo": redo_status})


# 変更画面の挿入処理
def composition_edit_add(request, product_id):
    current_composition_id = request.GET.get("current_composition_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    try:
        # エラーチェック
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない部品が指定されました。")
            # return JsonResponse({"exists": False})

        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりCompositionChangeSet、CompositionHistoryの値を再更新する。
            update_history_from_pointer(product_id)

            composition = Composition.objects.get(id=product_id)
            composition_change_set = CompositionChangeSet.objects.create(
                product=composition
            )

            current_composition = Composition.objects.get(
                pk=current_composition_id
            )
            new_composition_sort = current_composition.sort
            # current_composition.parent_idと同じ値かつ
            # current_composition.part以上の値のインスタンスを取得
            change_sort_instances = Composition.objects.filter(
                parent_id=current_composition.parent_id,
                sort__gte=current_composition.sort
            )
            # 取得したインスタンスの part_sort を更新して保存
            for instance in change_sort_instances:
                CompositionHistory.objects.create(
                    composition_change_set=composition_change_set,
                    composition_original_id=instance.id,
                    parent_original_id=instance.parent_id,
                    sort=instance.sort,
                    part=instance.part,
                    quantity=instance.quantity,
                    action='update',
                    status='before'
                )
                instance.sort += 1
                instance.save()
                CompositionHistory.objects.create(
                    composition_change_set=composition_change_set,
                    composition_original_id=instance.id,
                    parent_original_id=instance.parent_id,
                    sort=instance.sort,
                    part=instance.part,
                    quantity=instance.quantity,
                    action='update',
                    status='after'
                )

            # new_composition_instance = Composition()
            # edit_block_code を適切な PartMaster インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_composition_instance = Composition()
            # 正しい Part インスタンスを設定
            new_composition_instance.part = part_instance
            new_composition_instance.sort = new_composition_sort
            new_composition_instance.quantity = edit_block_quantity
            new_composition_instance.parent_id = current_composition.parent_id
            new_composition_instance.save()
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=new_composition_instance.id,
                parent_original_id=new_composition_instance.parent_id,
                sort=new_composition_instance.sort,
                part=new_composition_instance.part,
                quantity=new_composition_instance.quantity,
                action='create',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=composition,
                defaults={
                    'pointer': composition_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = composition_change_set
                pointer.save()

            # 更新された値よりcompositionに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")

    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})
    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"success": True,
                         "new_id": new_composition_instance.id,
                         "name": part_instance.name, "undo": undo_status,
                         "redo": redo_status})


# 変更画面の子の挿入処理
def composition_edit_add_children(request, product_id):
    current_composition_id = request.GET.get("current_composition_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    try:
        # エラーチェック
        #  if Part.objects.filter(code=edit_block_code).exists():
        #     exists = True
        if not Part.objects.filter(code=edit_block_code).exists():
            raise ValueError("存在しない部品が指定されました。")
        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりCompositionChangeSet、CompositionHistoryの値を再更新する。
            update_history_from_pointer(product_id)
            # 新しい CompositionChangeSet インスタンスを作成
            composition = Composition.objects.get(id=product_id)
            composition_change_set = CompositionChangeSet.objects.create(
                product=composition
            )
            current_composition = Composition.objects.get(
                pk=current_composition_id
            )
            # currentComposition.id == parentのComposition
            # かつその中で一番大きいsortの値を取得
            max_sort = Composition.objects.filter(
                parent_id=current_composition.id
            ).aggregate(Max('sort'))['sort__max']
            if max_sort is not None:
                new_composition_sort = max_sort + 1
            else:
                new_composition_sort = 1

            # edit_block_code を適切な Part インスタンスに変更する
            part_instance = Part.objects.get(code=edit_block_code)
            new_composition_instance = Composition()
            # 正しい Part インスタンスを設定
            new_composition_instance.part = part_instance
            new_composition_instance.sort = new_composition_sort
            new_composition_instance.quantity = edit_block_quantity
            # current_composition.idに該当するCompositionインスタンスを取得してそれを設定
            # new_composition_instance.parent_id = Composition.objects.get(pk=int(current_composition.id))
            # parent_instance = Part.objects.get(code=current_composition)
            new_composition_instance.parent_id = current_composition.id
            # new_composition_instance.parent = parent_instance
            new_composition_instance.save()
            # aaa = CompositionHistory.objects.create(
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=new_composition_instance.id,
                parent_original_id=new_composition_instance.parent_id,
                sort=new_composition_instance.sort,
                part=new_composition_instance.part,
                quantity=new_composition_instance.quantity,
                action='create',
                status='after'

            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=composition,
                defaults={
                    'pointer': composition_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = composition_change_set
                pointer.save()

            # 更新された値よりcompositionに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")

    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        # return JsonResponse({"exists": False})
        return JsonResponse({"success": False, "message": str(e)})

    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"success": True,
                         "new_id": new_composition_instance.id,
                         "name": part_instance.name,
                         "undo": undo_status,
                         "redo": redo_status
                         })


# 変更画面の変更処理
def composition_edit_mod(request, product_id):
    current_composition_id = request.GET.get("current_composition_id")
    edit_block_code = request.GET.get("edit_block_code")
    edit_block_quantity = request.GET.get("edit_block_quantity")
    # エラーチェック
    if Part.objects.filter(code=edit_block_code).exists():
        exists = True
        # 実行
        with transaction.atomic():
            # undoRedoPointerの値よりCompositionChangeSet、CompositionHistoryの値を再更新する。
            update_history_from_pointer(product_id)
            # 新しい CompositionChangeSet インスタンスを作成
            composition = Composition.objects.get(id=product_id)
            composition_change_set = CompositionChangeSet.objects.create(product=composition)
            current_composition = Composition.objects.get(pk=current_composition_id)
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=current_composition.id,
                parent_original_id=current_composition.parent_id,
                sort=current_composition.sort,
                part=current_composition.part,
                quantity=current_composition.quantity,
                action='update',
                status='before'
            )
            current_composition.quantity = edit_block_quantity
            current_composition.save()
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=current_composition.id,
                parent_original_id=current_composition.parent_id,
                sort=current_composition.sort,
                part=current_composition.part,
                quantity=current_composition.quantity,
                action='update',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=composition,
                defaults={
                    'pointer': composition_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = composition_change_set
                pointer.save()
    else:
        exists = False
    undo_status, redo_status = check_undo_redo(product_id)
    return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})


# 変更画面のドロップイベント
def composition_edit_drop(request, product_id):
    try:
        # 実行
        with transaction.atomic():
            update_history_from_pointer(product_id)
            # 新しい CompositionChangeSet インスタンスを作成
            composition = Composition.objects.get(id=product_id)
            composition_change_set = CompositionChangeSet.objects.create(product=composition)
            drop_target_id = request.GET.get("drop_target_id")    # 移動先のid
            insert_position = request.GET.get("insert_position")    # 移動先のidの前"before"、後"after"の情報
            dragged_id = request.GET.get("dragged_id")          # ドラッグした要素のid
            print('drop_target_id:', drop_target_id)
            print('insert_position:', insert_position)
            print('dragged_id:', dragged_id)
            # ドロップ先のインスタンスを取得
            drop_target_composition = Composition.objects.get(pk=drop_target_id)
            change_compositions = change_sorts(drop_target_composition, insert_position, dragged_id)

            # ドロップ先の後ろのソートを書き換える
            for change_composition in change_compositions:
                CompositionHistory.objects.create(
                    composition_change_set=composition_change_set,
                    composition_original_id=change_composition.id,
                    parent_original_id=change_composition.parent_id,
                    sort=change_composition.sort,
                    part=change_composition.part,
                    quantity=change_composition.quantity,
                    action='update',
                    status='before'
                )
                change_composition.sort += 1
                change_composition.save()
                CompositionHistory.objects.create(
                    composition_change_set=composition_change_set,
                    composition_original_id=change_composition.id,
                    parent_original_id=change_composition.parent_id,
                    sort=change_composition.sort,
                    part=change_composition.part,
                    quantity=change_composition.quantity,
                    action='update',
                    status='after'
                )
            # 移動元のparent,sortを書き換える
            dragged_composition = Composition.objects.get(pk=dragged_id)
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=dragged_composition.id,
                parent_original_id=dragged_composition.parent_id,
                sort=dragged_composition.sort,
                part=dragged_composition.part,
                quantity=dragged_composition.quantity,
                action='update',
                status='before'
            )
            dragged_composition.parent_id = drop_target_composition.parent_id
            if insert_position == 'before':
                dragged_composition.sort = drop_target_composition.sort
            else:
                dragged_composition.sort = drop_target_composition.sort + 1
            dragged_composition.save()
            CompositionHistory.objects.create(
                composition_change_set=composition_change_set,
                composition_original_id=dragged_composition.id,
                parent_original_id=dragged_composition.parent_id,
                sort=dragged_composition.sort,
                part=dragged_composition.part,
                quantity=dragged_composition.quantity,
                action='update',
                status='after'
            )
            # 指定したproductのUndoRedoPointerオブジェクトを取得
            pointer, created = UndoRedoPointer.objects.get_or_create(
                product=composition,
                defaults={
                    'pointer': composition_change_set
                }
            )
            # すでに存在する場合は、pointer_idを更新
            if not created:
                pointer.pointer = composition_change_set
                pointer.save()
            # 更新された値よりcompositionに循環参照が発生しているか
            # 確認し発生していたら、ロールバックしてエラーメッセージを戻す。
            if check_for_cyclic_parts(product_id):
                raise ValueError("循環参照エラーが発生致しました。")
    except ValueError as e:
        # ここではエラーがキャッチされますが、
        # withブロック内で例外が発生した場合、
        # 自動的にロールバックされています。
        # print(f"トランザクションがロールバックされました: {e}")
        return JsonResponse({"success": False, "message": str(e)})

    undo_status, redo_status = check_undo_redo(product_id)
    # return JsonResponse({"exists": exists, 'undo': undo_status, 'redo': redo_status})
    return JsonResponse({"success": True,
                         "undo": undo_status,
                         "redo": redo_status})


# ソート変更対象のidを格納する。
def change_sorts(drop_target_composition, insert_position, dragged_id):
    if insert_position == 'before':
        change_compositions = Composition.objects.filter(parent_id=drop_target_composition.parent_id,
                                                         sort__gte=drop_target_composition.sort
                                                         ).exclude(id=dragged_id)
    else:
        change_compositions = Composition.objects.filter(parent_id=drop_target_composition.parent_id,
                                                         sort__gt=drop_target_composition.sort
                                                         ).exclude(id=dragged_id)
    return change_compositions


# 変更画面の「元に戻す」ボタン処理
def composition_edit_undo(request, product_id):
    # 実行
    with transaction.atomic():
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
            # undo_redo_pointer.pointerのトランザクション処理を打ち消す。
            composition_historys = CompositionHistory.objects.filter(composition_change_set=undo_redo_pointer.pointer).order_by('-pk')
            for composition_history in composition_historys:
                # 作成
                if composition_history.action == 'create':
                    composition_to_delete = Composition.objects.get(pk=composition_history.composition_original_id)
                    composition_to_delete.delete()
                # 更新
                if composition_history.action == 'update' and composition_history.status == 'before':
                    composition_to_update = Composition.objects.get(pk=composition_history.composition_original_id)
                    composition_to_update.parent_id = composition_history.parent_original_id
                    composition_to_update.sort = composition_history.sort
                    composition_to_update.part = composition_history.part
                    composition_to_update.quantity = composition_history.quantity
                    composition_to_update.save()
                # 削除
                if composition_history.action == 'delete':
                    Composition.objects.create(
                        # historyのidから戻さないと整合性が取れない。
                        id=composition_history.composition_original_id,
                        parent_id=composition_history.parent_original_id,
                        sort=composition_history.sort,
                        part=composition_history.part,
                        quantity=composition_history.quantity,
                    )
            # 現状のポインタを１つ前のポインタへ戻す。
            composition = Composition.objects.get(pk=product_id)
            composition_change_set = CompositionChangeSet.objects.filter(
                product=composition, pk__lt=undo_redo_pointer.pointer.id
            ).order_by('-pk').first()
            # composition_change_setが取れなければundo_redo_pointerを削除。
            if composition_change_set is None:
                undo_redo_pointer.delete()
            else:
                undo_redo_pointer.pointer = composition_change_set
                undo_redo_pointer.save()
        except UndoRedoPointer.DoesNotExist:
            pass
        # 再描画の為のデータを取り出す。
        nodes = find_by_product_id(product_id)
        undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'part_list_app/composition_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status}
                  )


# 変更画面の「やり直し」ボタン処理
def composition_edit_redo(request, product_id):
    # 実行
    with transaction.atomic():
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
            # undo_redo_pointer.pointerのトランザクション処理を打ち消すを打ち消す。
            # composition_historys = CompositionHistory.objects.filter(composition_change_set=undo_redo_pointer.pointer).order_by('-pk')
            # pointerより大きい最初の１件を取り出す。
            composition = Composition.objects.get(pk=product_id)
            change_set = CompositionChangeSet.objects.filter(
                product=composition, pk__gt=undo_redo_pointer.pointer.id
            ).order_by('pk').first()
            redo_execute(change_set)
            # 現状のポインタを１つ後のポインタへ進める。
            composition = Composition.objects.get(pk=product_id)
            composition_change_set = CompositionChangeSet.objects.filter(
                product=composition, pk__gt=undo_redo_pointer.pointer.id
            ).order_by('pk').first()
            # composition_change_setが取れない時はここの関数はそもそも呼ばれない。
            if composition_change_set is None:
                pass
            else:
                undo_redo_pointer.pointer = composition_change_set
                undo_redo_pointer.save()
        except UndoRedoPointer.DoesNotExist:
            # undo_redo_pointerにレコードが存在しなくかつcomposition_change_set
            # に値が存在する場合、一番若いidの１件のchange_setよりredo処理を実行する。
            composition = Composition.objects.get(pk=product_id)
            change_set = CompositionChangeSet.objects.filter(
                product=composition
            ).order_by('pk').first()
            redo_execute(change_set)
            # 現状のポインタを１つ後のポインタへ進める。
            composition = Composition.objects.get(pk=product_id)
            composition_change_set = CompositionChangeSet.objects.filter(
                product=composition
            ).order_by('pk').first()
            # composition_change_setが取れない時はここの関数はそもそも呼ばれない。
            if composition_change_set is None:
                pass
            else:
                UndoRedoPointer.objects.create(
                    product=composition,
                    pointer=composition_change_set
                )
        # 再描画の為のデータを取り出す。
        nodes = find_by_product_id(product_id)
        # nodes = []
        # composition = Composition.objects.get(pk=product_id)
        # quantity = 1
        # usedquantity = 1
        # dict_data = {
        #     'id': composition.id,
        #     'code': composition.part.code,
        #     'name': composition.part.name,
        #     'quantity': quantity,
        #     'usedquantity': usedquantity,
        #     'children': get_children(composition.id, quantity)
        # }
        # nodes.append(dict_data)
        undo_status, redo_status = check_undo_redo(product_id)
    return render(request,
                  'part_list_app/composition_edit.html',   # 使用するテンプレート
                  {'product_id': product_id, 'nodes': nodes, 'undo': undo_status, 'redo': redo_status}
                  )


def redo_execute(change_set):
    composition_historys = CompositionHistory.objects.filter(composition_change_set=change_set).order_by('pk')
    for composition_history in composition_historys:
        # 作成
        if composition_history.action == 'create':
            Composition.objects.create(
                # historyのidから戻さないと整合性が取れない。
                id=composition_history.composition_original_id,
                parent_id=composition_history.parent_original_id,
                sort=composition_history.sort,
                part=composition_history.part,
                quantity=composition_history.quantity,
            )
        # 更新
        if composition_history.action == 'update' and composition_history.status == 'after':
            composition_to_update = Composition.objects.get(pk=composition_history.composition_original_id)
            composition_to_update.parent_id = composition_history.parent_original_id
            composition_to_update.sort = composition_history.sort
            composition_to_update.part = composition_history.part
            composition_to_update.quantity = composition_history.quantity
            composition_to_update.save()
        # 削除
        if composition_history.action == 'delete':
            composition_to_delete = Composition.objects.get(pk=composition_history.composition_original_id)
            composition_to_delete.delete()


# undoRedoPointerの値よりCompositionChangeSet、CompositionHistoryの値を再更新する。
def update_history_from_pointer(product_id):
    # ポインタより大きな値のCompositionChangeSet、CompositionHistoryインスタンスがあればそちらは削除する。
    # その後、新しいCompositionChangeSet、CompositionHistoryインスタンスを追加する。
    try:
        undo_redo_pointer = UndoRedoPointer.objects.get(product=product_id)
        composition_change_sets = CompositionChangeSet.objects.filter(
            product=undo_redo_pointer.product,
            id__gt=undo_redo_pointer.pointer.id
        )
        for change_set in composition_change_sets:
            # 以下はForeignKeyでcomposition_change_setつながっているのであえて削除しなくても
            # composition_change_setが削除されるとこちらも消えるはず。
            # CompositionHistory.objects.filter(composition_change_set=change_set).delete()
            change_set.delete()
    except UndoRedoPointer.DoesNotExist:
        # UndoRedoPointerが存在しないけれどもCompositionChangeSet、CompositionHistoryが存在する場合
        # CompositionChangeSet、CompositionHistoryを削除する。
        composition = Composition.objects.get(id=product_id)
        composition_change_sets = CompositionChangeSet.objects.filter(
            product=composition
        )
        for change_set in composition_change_sets:
            # 以下はForeignKeyでcomposition_change_setつながっているのであえて削除しなくても
            # composition_change_setが削除されるとこちらも消えるはず。
            # CompositionHistory.objects.filter(composition_change_set=change_set).delete()
            change_set.delete()


def check_undo_redo(product_id):
    if product_id is None:
        undo = False
        redo = False
    else:
        # product_idよりUndoRedoPointerを参照
        # データが存在する場合、undo変数をTrue
        # データが存在しない場合、undo変数をFalse
        # データが存在しかつpointerより大きい値のCompositionChangeSetのidが存在する場合、redo変数をTrueにする。
        # データが存在しかつpointerより大きい値のCompositionChangeSetのidが存在しない場合、redo変数をFalseにする。
        # データが存在しないかつCompositionChangeSetが存在する場合、redo変数をTrueにする。
        # データが存在しないかつCompositionChangeSetが存在しない場合、redo変数をFalseにする。
        composition = Composition.objects.get(pk=product_id)
        try:
            undo_redo_pointer = UndoRedoPointer.objects.get(product=composition)
            undo = True
            entries = CompositionChangeSet.objects.filter(product=composition, pk__gt=undo_redo_pointer.pointer.id)
            if entries.exists():
                redo = True
            else:
                redo = False
        except UndoRedoPointer.DoesNotExist:
            undo = False
            entries = CompositionChangeSet.objects.filter(product=composition)
            if entries.exists():
                redo = True
            else:
                redo = False

    return undo, redo


def find_by_product_id(product_id):
    nodes = []
    composition = Composition.objects.get(pk=product_id)
    quantity = 1
    usedquantity = 1
    dict_data = {
        'id': composition.id,
        'code': composition.part.code,
        'name': composition.part.name,
        'quantity': quantity,
        'usedquantity': usedquantity,
        'children': get_children(composition.id, quantity)
    }
    nodes.append(dict_data)
    return nodes


# 一覧画面の削除処理
def product_del(request):
    # GETパラメータから selectedIds を取得
    selected_ids_str = request.GET.get('selectedIds', '')
    # 実行
    with transaction.atomic():
        # カンマで区切られた文字列をリストに変換
        selected_ids_list = selected_ids_str.split(',') if selected_ids_str else []
        # 選択されたIDのリストをループして処理
        for id_str in selected_ids_list:
            # 選択行のインスタンスを取得
            current_composition = Composition.objects.get(pk=id_str)
            # 選択された行のidの子を取得する。
            children_data = delete_childrens(current_composition.id)
            # 取得された子のデータをフラットにしてならべる
            all_children = get_all_children(children_data)
            # 全ての子を削除する
            for child in all_children:
                child_composition = Composition.objects.get(pk=child['id'])
                child_composition.delete()
            current_composition.delete()
    # ProductListビューにリダイレクト
    return HttpResponseRedirect(reverse('part_list_app:product_list'))


def is_cyclic_part(id, part_id, visited_parts):
    """
    部品の循環参照をチェックするためのヘルパー関数
    :param id: 現在調べているCompositionオブジェクトのID
    :param part_id: 現在調べている部品のID
    :param visited_parts: これまでに訪れた部品のIDのセット
    :return: 循環が存在する場合はTrue、それ以外はFalse
    """
    if part_id in visited_parts:
        return True  # 現在の部品が以前に訪れた部品のリストに存在する場合、循環参照が存在する

    visited_parts.add(part_id)

    # 現在の部品の子部品をチェック
    compositions = Composition.objects.filter(parent_id=id).order_by('sort')
    for composition in compositions:
        if is_cyclic_part(composition.id, composition.part.id, visited_parts):
            return True

    visited_parts.remove(part_id)
    return False


def check_for_cyclic_parts(product_id):
    """
    指定された製品IDについて部品の循環参照をチェックする
    :param product_id: 製品ID
    :return: 循環が存在する場合はTrue、それ以外はFalse
    """
    composition = Composition.objects.get(pk=product_id)
    return is_cyclic_part(composition.id, composition.part.id, set())
