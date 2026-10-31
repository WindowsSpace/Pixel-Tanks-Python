# Столкновения по маскам


import pygame


def hitbox_collide(sprite1, sprite2) -> bool:
    # Маски пересекаются только если пересекаются rect'ы
    if not sprite1.rect.colliderect(sprite2.rect):
        return False
    return pygame.sprite.collide_mask(sprite1, sprite2) is not None

def bullet_collide(sprite1, sprite2):
    rect1 = sprite1.rect.inflate(0, 1)
    rect2 = sprite2.rect.inflate(0, 1)
    return rect1.colliderect(rect2)
